import ast
import os
import time
from pathlib import Path
from collections import defaultdict
from core.mutation_logger import MutationLogger

class ConsolidationScorer:
    """
    Standalone scoring utility that evaluates modules based on usage frequency,
    failure rates, dependency count, and age. Returns a normalized score (0-100).
    """

    def __init__(self, project_root: str = ".", cycle_counter: int = 0):
        self.project_root = Path(project_root).resolve()
        self.cycle_counter = cycle_counter
        self.usage_tracker = defaultdict(int)  # module_path -> usage count
        self.failure_logger = MutationLogger()
        self._scan_imports()

    def _scan_imports(self):
        """Scan all Python files in the project to track import usage frequency."""
        for py_file in self.project_root.rglob("*.py"):
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=str(py_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.usage_tracker[alias.name] += 1
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            self.usage_tracker[node.module] += 1
            except (SyntaxError, UnicodeDecodeError, IOError):
                continue

    def _count_dependencies(self, module_path: Path) -> int:
        """Count the number of import and from-import statements in a module."""
        try:
            with open(module_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(module_path))
        except (SyntaxError, UnicodeDecodeError, IOError):
            return 0
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                count += 1
        return count

    def _compute_failure_rate(self, module_name: str) -> float:
        """Compute failure rate from mutation logs for a given module."""
        try:
            logs = self.failure_logger.get_logs(module_name)
            if not logs:
                return 0.0
            failures = sum(1 for log in logs if log.get("status") == "failure")
            return failures / len(logs)
        except Exception:
            return 0.0

    def _compute_age(self, module_path: Path) -> float:
        """
        Compute age based on file modification timestamp relative to cycle counter.
        Returns a value between 0 and 1 (0 = very old, 1 = very recent).
        """
        try:
            mtime = os.path.getmtime(module_path)
            current_time = time.time()
            # Simulate age based on cycle counter (if provided, use it as reference)
            if self.cycle_counter > 0:
                # Assume each cycle is 1 hour (3600 seconds)
                cycle_seconds = self.cycle_counter * 3600
                age_seconds = current_time - mtime
                # Normalize: if age > cycle_seconds, it's old; else recent
                if age_seconds >= cycle_seconds:
                    return 0.0
                else:
                    return 1.0 - (age_seconds / cycle_seconds)
            else:
                # Without cycle counter, just return a simple recency factor
                age_seconds = current_time - mtime
                # Assume 30 days (2,592,000 seconds) as max age
                max_age = 2592000
                if age_seconds >= max_age:
                    return 0.0
                else:
                    return 1.0 - (age_seconds / max_age)
        except OSError:
            return 0.0

    def score_module(self, module_path: Path) -> float:
        """
        Compute a normalized score (0-100) for a single module.
        Combines usage frequency, failure rate, dependency count, and age.
        """
        module_name = module_path.stem  # e.g., 'my_module' from 'my_module.py'
        module_key = str(module_path.relative_to(self.project_root)).replace(os.sep, '.').rstrip('.py')

        # 1. Usage frequency (0-25 points)
        usage_count = self.usage_tracker.get(module_key, 0)
        max_usage = max(self.usage_tracker.values()) if self.usage_tracker else 1
        usage_score = (usage_count / max_usage) * 25

        # 2. Failure rate (0-25 points, inverted: lower failure rate is better)
        failure_rate = self._compute_failure_rate(module_name)
        failure_score = (1 - failure_rate) * 25

        # 3. Dependency count (0-25 points, more dependencies = higher score)
        dep_count = self._count_dependencies(module_path)
        # Assume max dependencies is 50 for normalization
        max_deps = 50
        dep_score = min(dep_count / max_deps, 1.0) * 25

        # 4. Age (0-25 points, more recent = higher score)
        age_factor = self._compute_age(module_path)
        age_score = age_factor * 25

        # Normalize to 0-100
        total_score = usage_score + failure_score + dep_score + age_score
        return min(total_score, 100.0)

    def score_all_modules(self) -> dict:
        """
        Score all Python modules in the project root.
        Returns a dict mapping module path (str) to score (float).
        """
        scores = {}
        for py_file in self.project_root.rglob("*.py"):
            # Skip __init__.py and non-module files if desired
            if py_file.name == "__init__.py":
                continue
            scores[str(py_file)] = self.score_module(py_file)
        return scores


if __name__ == "__main__":
    # Example usage
    scorer = ConsolidationScorer(project_root=".", cycle_counter=10)
    all_scores = scorer.score_all_modules()
    for module, score in sorted(all_scores.items(), key=lambda x: x[1], reverse=True):
        print(f"{module}: {score:.2f}")