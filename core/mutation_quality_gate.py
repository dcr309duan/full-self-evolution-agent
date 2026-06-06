import ast
import sys
import subprocess
import traceback
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import importlib.util
import json
from datetime import datetime


@dataclass
class QualityGateResult:
    """Tracks the result of quality gate checks."""
    passed: bool = False
    errors: List[Dict[str, Any]] = field(default_factory=list)
    retry_count: int = 0
    feedback_prompt: str = ""
    high_risk: bool = False
    requires_review: bool = False
    feature_vectors: List[Dict[str, Any]] = field(default_factory=list)


class MutationQualityGate:
    """
    Four-stage quality gate for mutation patches:
    1. Pre-mutation validation (syntax + import check) - FIRST gate
    2. Static analysis (mypy preferred, fallback to pyflakes/py_compile)
    3. Minimal integration smoke test (import patched module)
    4. Test history check (queries test registry for existing tests)
    Retry logic: up to 3 attempts per stage, collects error details for LLM feedback.
    """

    MAX_RETRIES = 3

    def __init__(self, project_root: str = ".", test_registry_path: str = "test_registry.json"):
        self.project_root = Path(project_root).resolve()
        self.test_registry_path = Path(test_registry_path)
        self.errors: List[Dict[str, Any]] = []
        self.feature_vectors: List[Dict[str, Any]] = []

    def _reset_errors(self) -> None:
        self.errors = []
        self.feature_vectors = []

    def _classify_error(self, stage: str, message: str, detail: str = "") -> str:
        """Classify an error into a category for structured feedback."""
        # Check for syntax errors
        if stage == "syntax" or stage == "pre_mutation_syntax":
            return "syntax"
        
        # Check for import errors
        if "ImportError" in message or "ModuleNotFoundError" in message or "import" in message.lower() or stage == "pre_mutation_import":
            return "import"
        
        # Check for type errors
        if "TypeError" in message or "type" in message.lower() or "mypy" in message.lower():
            return "type"
        
        # Check for runtime errors
        if "RuntimeError" in message or "Exception" in message or "Error" in message:
            return "runtime"
        
        # Check for test history errors
        if stage == "test_history_check":
            return "test_history"
        
        # Default to 'other'
        return "other"

    def _determine_severity(self, stage: str, category: str, attempt: int) -> str:
        """Determine severity level based on stage, category, and attempt number."""
        if category == "syntax" or category == "import":
            if attempt == 1:
                return "critical"
            return "error"
        if category == "type":
            return "error"
        if category == "runtime":
            if attempt >= self.MAX_RETRIES:
                return "critical"
            return "error"
        if category == "test_history":
            return "warning"
        return "warning"

    def _log_rejection(self, mutation_id: str, errors: List[Dict[str, Any]]) -> None:
        """Log rejection details to a structured JSON file."""
        log_dir = Path("logs/rejected_mutations")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "mutation_id": mutation_id,
            "error_details": errors
        }
        
        log_file = log_dir / f"rejection_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
        with open(log_file, 'w') as f:
            json.dump(log_entry, f, indent=2)

    def _extract_complexity(self, code: str) -> int:
        """Extract cyclomatic complexity from code."""
        try:
            tree = ast.parse(code)
            complexity = 1  # Base complexity
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With)):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
                elif isinstance(node, ast.Try):
                    complexity += len(node.handlers)
            return complexity
        except SyntaxError:
            return 0

    def _extract_import_count(self, code: str) -> int:
        """Extract number of imports from code."""
        try:
            tree = ast.parse(code)
            count = 0
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    count += 1
            return count
        except SyntaxError:
            return 0

    def _extract_file_count(self, code: str) -> int:
        """Extract number of files referenced in imports."""
        try:
            tree = ast.parse(code)
            files = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        files.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        files.add(node.module.split('.')[0])
            return len(files)
        except SyntaxError:
            return 0

    def _extract_goal_type(self, code: str) -> str:
        """Extract the goal type from code comments or structure."""
        # Look for common goal type indicators in comments
        goal_types = {
            "performance": ["optimize", "faster", "speed", "performance"],
            "security": ["secure", "vulnerability", "injection", "sanitize"],
            "readability": ["readable", "clear", "simplify", "refactor"],
            "correctness": ["fix", "bug", "error", "correct"],
            "feature": ["add", "implement", "new", "feature"],
        }
        
        try:
            # Check comments for goal type hints
            for node in ast.walk(ast.parse(code)):
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                    comment = node.value.value
                    if isinstance(comment, str):
                        for goal_type, keywords in goal_types.items():
                            if any(keyword in comment.lower() for keyword in keywords):
                                return goal_type
            
            # Check function names for goal type hints
            for node in ast.walk(ast.parse(code)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for goal_type, keywords in goal_types.items():
                        if any(keyword in node.name.lower() for keyword in keywords):
                            return goal_type
        except SyntaxError:
            pass
        
        return "unknown"

    def _build_feature_vector(self, stage: str, attempt: int, message: str, detail: str = "", 
                             code: str = "", line: Optional[int] = None) -> Dict[str, Any]:
        """Build a structured feature vector for a failure."""
        category = self._classify_error(stage, message, detail)
        severity = self._determine_severity(stage, category, attempt)
        vector = {
            "stage": stage,
            "attempt": attempt,
            "message": message,
            "detail": detail,
            "category": category,
            "severity": severity,
            "complexity": self._extract_complexity(code) if code else 0,
            "import_count": self._extract_import_count(code) if code else 0,
            "file_count": self._extract_file_count(code) if code else 0,
            "goal_type": self._extract_goal_type(code) if code else "unknown",
        }
        if line is not None:
            vector["line"] = line
        return vector

    def _record_error(self, stage: str, attempt: int, message: str, detail: str = "", 
                     line: Optional[int] = None, code: str = "") -> None:
        error_category = self._classify_error(stage, message, detail)
        severity = self._determine_severity(stage, error_category, attempt)
        error_entry = {
            "stage": stage,
            "attempt": attempt,
            "message": message,
            "detail": detail,
            "category": error_category,
            "severity": severity,
        }
        if line is not None:
            error_entry["line"] = line
        self.errors.append(error_entry)
        
        # Build and store feature vector
        feature_vector = self._build_feature_vector(stage, attempt, message, detail, code, line)
        self.feature_vectors.append(feature_vector)

    def _format_feedback(self) -> str:
        """Format collected errors for LLM feedback."""
        if not self.errors:
            return "All quality checks passed."
        lines = ["Quality gate failures:"]
        for err in self.errors:
            line_info = f" (line {err['line']})" if "line" in err else ""
            category_info = f" [category: {err['category']}]" if "category" in err else ""
            severity_info = f" [severity: {err['severity']}]" if "severity" in err else ""
            lines.append(f"  Stage '{err['stage']}' (attempt {err['attempt']}){line_info}{category_info}{severity_info}: {err['message']}")
            if err.get("detail"):
                lines.append(f"    Detail: {err['detail']}")
        return "\n".join(lines)

    def _build_feedback_prompt(self) -> str:
        """Build a concise feedback prompt for LLM re-prompting."""
        if not self.errors:
            return "No errors to fix."
        prompt_parts = ["Please fix the following errors in the patch code:"]
        for err in self.errors:
            line_info = f" at line {err['line']}" if "line" in err else ""
            category_info = f" [category: {err['category']}]" if "category" in err else ""
            severity_info = f" [severity: {err['severity']}]" if "severity" in err else ""
            prompt_parts.append(f"- Stage '{err['stage']}' (attempt {err['attempt']}){line_info}{category_info}{severity_info}: {err['message']}")
            if err.get("detail"):
                # Truncate long details for prompt brevity
                detail = err["detail"]
                if len(detail) > 200:
                    detail = detail[:200] + "..."
                prompt_parts.append(f"  Detail: {detail}")
        return "\n".join(prompt_parts)

    def pre_mutation_validator(self, mutation_code: str) -> bool:
        """
        Pre-mutation validation using ast.parse to validate syntax of proposed code changes.
        Also checks if all imported modules exist in the project.
        Returns True if all checks pass, False otherwise.
        """
        # Stage 1: Syntax validation
        try:
            tree = ast.parse(mutation_code)
        except SyntaxError as e:
            line_no = e.lineno if e.lineno is not None else 0
            self._record_error("pre_mutation_syntax", 1, f"Syntax error: {e.msg}", str(e), line=line_no, code=mutation_code)
            return False

        # Stage 2: Import resolution
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    if not self._check_module_exists(module_name):
                        self._record_error("pre_mutation_import", 1, 
                                         f"Module '{module_name}' not found in project",
                                         f"Import at line {node.lineno}", code=mutation_code)
                        return False
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module if node.module else ""
                if module_name and not self._check_module_exists(module_name):
                    self._record_error("pre_mutation_import", 1,
                                     f"Module '{module_name}' not found in project",
                                     f"Import from at line {node.lineno}", code=mutation_code)
                    return False

        return True

    def _check_module_exists(self, module_name: str) -> bool:
        """
        Check if a module exists in the project or is a standard library module.
        Returns True if the module can be found, False otherwise.
        """
        # Check if it's a standard library module
        if module_name in sys.builtin_module_names:
            return True
        
        # Check if it's a standard library module by trying to find its spec
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is not None:
                # Check if the module is within the project root
                if spec.origin:
                    module_path = Path(spec.origin).resolve()
                    if self.project_root in module_path.parents or module_path == self.project_root:
                        return True
                    # Also check if it's a standard library module
                    if 'site-packages' not in str(module_path) and 'dist-packages' not in str(module_path):
                        return True
                return True
        except (ImportError, ValueError, AttributeError):
            pass
        
        # Check if the module file exists in the project
        module_path = self.project_root / module_name.replace('.', '/')
        if module_path.exists():
            return True
        if (module_path / '__init__.py').exists():
            return True
        if module_path.with_suffix('.py').exists():
            return True
        
        return False

    def check_syntax(self, patch_code: str) -> bool:
        """Stage 1: Syntax check using ast.parse()."""
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                ast.parse(patch_code)
                return True
            except SyntaxError as e:
                line_no = e.lineno if e.lineno is not None else 0
                self._record_error("syntax", attempt, f"Syntax error: {e.msg}", str(e), line=line_no, code=patch_code)
                if attempt < self.MAX_RETRIES:
                    # Minor fix attempt: try to strip trailing whitespace issues
                    patch_code = patch_code.rstrip() + "\n"
                else:
                    return False
        return False

    def check_static_analysis(self, file_path: str) -> bool:
        """Stage 2: Static analysis. Try mypy, fallback to pyflakes, then py_compile."""
        file_path = str(self.project_root / file_path)
        for attempt in range(1, self.MAX_RETRIES + 1):
            # Try mypy first
            try:
                result = subprocess.run(
                    ["mypy", "--show-error-codes", file_path],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    return True
                # Extract line numbers from mypy output if possible
                error_lines = []
                for line in (result.stdout + result.stderr).splitlines():
                    if ":" in line and file_path in line:
                        parts = line.split(":")
                        if len(parts) >= 2 and parts[1].strip().isdigit():
                            error_lines.append(int(parts[1].strip()))
                line_no = error_lines[0] if error_lines else None
                self._record_error("static_analysis", attempt,
                                   f"mypy found issues", result.stdout + result.stderr, line=line_no)
            except FileNotFoundError:
                pass  # mypy not installed, fall through
            except subprocess.TimeoutExpired:
                self._record_error("static_analysis", attempt, "mypy timed out")

            # Fallback to pyflakes
            try:
                result = subprocess.run(
                    ["pyflakes", file_path],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0:
                    return True
                # Extract line numbers from pyflakes output
                error_lines = []
                for line in (result.stdout + result.stderr).splitlines():
                    if ":" in line and file_path in line:
                        parts = line.split(":")
                        if len(parts) >= 2 and parts[1].strip().isdigit():
                            error_lines.append(int(parts[1].strip()))
                line_no = error_lines[0] if error_lines else None
                self._record_error("static_analysis", attempt,
                                   f"pyflakes found issues", result.stdout + result.stderr, line=line_no)
            except FileNotFoundError:
                pass
            except subprocess.TimeoutExpired:
                self._record_error("static_analysis", attempt, "pyflakes timed out")

            # Final fallback: py_compile
            try:
                import py_compile
                py_compile.compile(file_path, doraise=True)
                return True
            except py_compile.PyCompileError as e:
                line_no = e.lineno if hasattr(e, 'lineno') and e.lineno is not None else None
                self._record_error("static_analysis", attempt,
                                   f"py_compile error", str(e), line=line_no)
                if attempt == self.MAX_RETRIES:
                    return False
                # Retry: could re-read file (in case of concurrent modification)
                continue
        return False

    def check_smoke_test(self, module_import_path: str) -> bool:
        """Stage 3: Minimal integration smoke test by importing the module."""
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # Ensure the module path is in sys.path
                sys.path.insert(0, str(self.project_root))
                # Convert file path to module import path (e.g., "core/mutation_quality_gate.py" -> "core.mutation_quality_gate")
                module_name = module_import_path.replace("/", ".").replace("\\", ".").rstrip(".py")
                __import__(module_name)
                # Basic smoke: check it has a main class or function
                mod = sys.modules[module_name]
                # If the module defines a callable or class, try to instantiate it
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if callable(attr) and not attr_name.startswith("_"):
                        # Try calling with no args (simple smoke)
                        try:
                            result = attr()
                            if result is not None:
                                break  # smoke passed
                        except Exception:
                            continue  # not a simple constructor, skip
                return True
            except Exception as e:
                # Try to extract line number from traceback
                tb = traceback.extract_tb(sys.exc_info()[2])
                line_no = tb[-1].lineno if tb else None
                self._record_error("smoke_test", attempt,
                                   f"Import or smoke test failed: {e}",
                                   traceback.format_exc(), line=line_no)
                if attempt < self.MAX_RETRIES:
                    # Clean up sys.path and retry
                    if str(self.project_root) in sys.path:
                        sys.path.remove(str(self.project_root))
                    # Remove any partially loaded module
                    module_name = module_import_path.replace("/", ".").replace("\\", ".").rstrip(".py")
                    if module_name in sys.modules:
                        del sys.modules[module_name]
                else:
                    return False
        return False

    def check_test_history(self, module_import_path: str) -> Tuple[bool, bool, bool]:
        """
        Stage 4: Test history check. Queries the test registry for existing tests related to the modules being mutated.
        Returns a tuple of (passed, high_risk, requires_review).
        - If a test exists and previously passed, skip regeneration (returns passed=True).
        - If a test exists and previously failed, flag as high-risk and require manual review.
        - If no test exists, continue normally.
        """
        if not self.test_registry_path.exists():
            # No test registry, continue normally
            return True, False, False

        try:
            with open(self.test_registry_path, 'r') as f:
                registry = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self._record_error("test_history_check", 1, f"Failed to read test registry: {e}", str(e))
            return False, False, False

        # Convert module import path to a module name for lookup
        module_name = module_import_path.replace("/", ".").replace("\\", ".").rstrip(".py")
        
        # Look for tests related to this module
        for entry in registry:
            if entry.get("module_name") == module_name or entry.get("module_import_path") == module_import_path:
                test_status = entry.get("status", "unknown")
                if test_status == "passed":
                    # Test exists and previously passed, skip regeneration
                    return True, False, False
                elif test_status == "failed":
                    # Test exists and previously failed, flag as high-risk
                    self._record_error("test_history_check", 1, 
                                     f"Existing test for module '{module_name}' previously failed",
                                     f"Test file: {entry.get('test_file_path', 'unknown')}, "
                                     f"Test function: {entry.get('test_function_name', 'unknown')}")
                    return False, True, True
                else:
                    # Unknown status, continue normally
                    return True, False, False

        # No existing test found, continue normally
        return True, False, False

    def run_all_checks(self, patch_code: str, file_path: str, module_import_path: str, mutation_id: str = "unknown") -> QualityGateResult:
        """
        Run all four stages sequentially. Returns a QualityGateResult with detailed feedback.
        Pre-mutation validation is the FIRST gate before any other checks.
        """
        self._reset_errors()
        total_retries = 0
        high_risk = False
        requires_review = False

        # Stage 0: Pre-mutation validation (FIRST gate)
        if not self.pre_mutation_validator(patch_code):
            total_retries += sum(1 for e in self.errors if "pre_mutation" in e["stage"])
            # Log rejection with full error details
            self._log_rejection(mutation_id, list(self.errors))
            return QualityGateResult(
                passed=False,
                errors=list(self.errors),
                retry_count=total_retries,
                feedback_prompt=self._build_feedback_prompt(),
                feature_vectors=list(self.feature_vectors)
            )

        # Stage 1: Syntax check (only if pre-mutation passed)
        if not self.check_syntax(patch_code):
            total_retries += sum(1 for e in self.errors if e["stage"] == "syntax")
            self._log_rejection(mutation_id, list(self.errors))
            return QualityGateResult(
                passed=False,
                errors=list(self.errors),
                retry_count=total_retries,
                feedback_prompt=self._build_feedback_prompt(),
                feature_vectors=list(self.feature_vectors)
            )

        # Stage 2: Static analysis (only if syntax passed)
        if not self.check_static_analysis(file_path):
            total_retries += sum(1 for e in self.errors if e["stage"] == "static_analysis")
            self._log_rejection(mutation_id, list(self.errors))
            return QualityGateResult(
                passed=False,
                errors=list(self.errors),
                retry_count=total_retries,
                feedback_prompt=self._build_feedback_prompt(),
                feature_vectors=list(self.feature_vectors)
            )

        # Stage 3: Smoke test
        if not self.check_smoke_test(module_import_path):
            total_retries += sum(1 for e in self.errors if e["stage"] == "smoke_test")
            self._log_rejection(mutation_id, list(self.errors))
            return QualityGateResult(
                passed=False,
                errors=list(self.errors),
                retry_count=total_retries,
                feedback_prompt=self._build_feedback_prompt(),
                feature_vectors=list(self.feature_vectors)
            )

        # Stage 4: Test history check
        test_history_passed, test_history_high_risk, test_history_requires_review = self.check_test_history(module_import_path)
        if not test_history_passed:
            total_retries += sum(1 for e in self.errors if e["stage"] == "test_history_check")
            high_risk = test_history_high_risk
            requires_review = test_history_requires_review
            self._log_rejection(mutation_id, list(self.errors))
            return QualityGateResult(
                passed=False,
                errors=list(self.errors),
                retry_count=total_retries,
                feedback_prompt=self._build_feedback_prompt(),
                high_risk=high_risk,
                requires_review=requires_review,
                feature_vectors=list(self.feature_vectors)
            )

        return QualityGateResult(
            passed=True,
            errors=[],
            retry_count=total_retries,
            feedback_prompt="All quality checks passed.",
            high_risk=high_risk,
            requires_review=requires_review,
            feature_vectors=list(self.feature_vectors)
        )

    def get_error_categorization_for_selector(self) -> List[Dict[str, Any]]:
        """
        Returns the error categorization results (feature vectors) for the failure_aware_selector.
        This method provides real-time feedback on mutation outcomes by returning the collected
        feature vectors with error categories, which can be used for training the selector.
        """
        return list(self.feature_vectors)

    def get_last_feature_vectors(self) -> List[Dict[str, Any]]:
        """
        Returns the feature vectors from the last mutation attempt.
        This method is called by the diversity tracker to get the feature vectors
        for the most recent mutation attempt.
        """
        return list(self.feature_vectors)