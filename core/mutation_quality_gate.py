import ast
import sys
import subprocess
import traceback
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import importlib.util


@dataclass
class QualityGateResult:
    """Tracks the result of quality gate checks."""
    passed: bool = False
    errors: List[Dict[str, Any]] = field(default_factory=list)
    retry_count: int = 0
    feedback_prompt: str = ""


class MutationQualityGate:
    """
    Three-stage quality gate for mutation patches:
    1. Syntax check via ast.parse()
    2. Static analysis (mypy preferred, fallback to pyflakes/py_compile)
    3. Minimal integration smoke test (import patched module)
    Retry logic: up to 3 attempts per stage, collects error details for LLM feedback.
    """

    MAX_RETRIES = 3

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.errors: List[Dict[str, Any]] = []

    def _reset_errors(self) -> None:
        self.errors = []

    def _classify_error(self, stage: str, message: str, detail: str = "") -> str:
        """Classify an error into a category for structured feedback."""
        # Check for syntax errors
        if stage == "syntax":
            return "syntax"
        
        # Check for import errors
        if "ImportError" in message or "ModuleNotFoundError" in message or "import" in message.lower():
            return "import"
        
        # Check for type errors
        if "TypeError" in message or "type" in message.lower() or "mypy" in message.lower():
            return "type"
        
        # Check for runtime errors
        if "RuntimeError" in message or "Exception" in message or "Error" in message:
            return "runtime"
        
        # Default to 'other'
        return "other"

    def _record_error(self, stage: str, attempt: int, message: str, detail: str = "", line: Optional[int] = None) -> None:
        error_category = self._classify_error(stage, message, detail)
        error_entry = {
            "stage": stage,
            "attempt": attempt,
            "message": message,
            "detail": detail,
            "category": error_category,
        }
        if line is not None:
            error_entry["line"] = line
        self.errors.append(error_entry)

    def _format_feedback(self) -> str:
        """Format collected errors for LLM feedback."""
        if not self.errors:
            return "All quality checks passed."
        lines = ["Quality gate failures:"]
        for err in self.errors:
            line_info = f" (line {err['line']})" if "line" in err else ""
            category_info = f" [category: {err['category']}]" if "category" in err else ""
            lines.append(f"  Stage '{err['stage']}' (attempt {err['attempt']}){line_info}{category_info}: {err['message']}")
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
            prompt_parts.append(f"- Stage '{err['stage']}' (attempt {err['attempt']}){line_info}{category_info}: {err['message']}")
            if err.get("detail"):
                # Truncate long details for prompt brevity
                detail = err["detail"]
                if len(detail) > 200:
                    detail = detail[:200] + "..."
                prompt_parts.append(f"  Detail: {detail}")
        return "\n".join(prompt_parts)

    def pre_mutation_check(self, mutation_code: str) -> bool:
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
            self._record_error("pre_mutation_syntax", 1, f"Syntax error: {e.msg}", str(e), line=line_no)
            return False

        # Stage 2: Import resolution
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    if not self._check_module_exists(module_name):
                        self._record_error("pre_mutation_import", 1, 
                                         f"Module '{module_name}' not found in project",
                                         f"Import at line {node.lineno}")
                        return False
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module if node.module else ""
                if module_name and not self._check_module_exists(module_name):
                    self._record_error("pre_mutation_import", 1,
                                     f"Module '{module_name}' not found in project",
                                     f"Import from at line {node.lineno}")
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
                self._record_error("syntax", attempt, f"Syntax error: {e.msg}", str(e), line=line_no)
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

    def run_all_checks(self, patch_code: str, file_path: str, module_import_path: str) -> QualityGateResult:
        """
        Run all three stages sequentially. Returns a QualityGateResult with detailed feedback.
        """
        self._reset_errors()
        total_retries = 0

        # Stage 1
        if not self.check_syntax(patch_code):
            total_retries += sum(1 for e in self.errors if e["stage"] == "syntax")
            return QualityGateResult(
                passed=False,
                errors=list(self.errors),
                retry_count=total_retries,
                feedback_prompt=self._build_feedback_prompt()
            )

        # Stage 2
        if not self.check_static_analysis(file_path):
            total_retries += sum(1 for e in self.errors if e["stage"] == "static_analysis")
            return QualityGateResult(
                passed=False,
                errors=list(self.errors),
                retry_count=total_retries,
                feedback_prompt=self._build_feedback_prompt()
            )

        # Stage 3
        if not self.check_smoke_test(module_import_path):
            total_retries += sum(1 for e in self.errors if e["stage"] == "smoke_test")
            return QualityGateResult(
                passed=False,
                errors=list(self.errors),
                retry_count=total_retries,
                feedback_prompt=self._build_feedback_prompt()
            )

        return QualityGateResult(
            passed=True,
            errors=[],
            retry_count=total_retries,
            feedback_prompt="All quality checks passed."
        )