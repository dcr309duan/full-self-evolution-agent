import os
import ast
import math
from collections import Counter
from typing import Dict, List, Tuple, Optional

class TestDiversityScorer:
    """
    Scores a test suite's diversity based on:
    1. Number of unique modules tested
    2. Distribution of test sizes (number of test functions per file)
    3. Presence of edge case tests (empty input, error handling)
    """

    def __init__(self, test_dir: str = "tests"):
        self.test_dir = test_dir
        self.edge_case_keywords = {
            "empty": ["empty", "null", "none", "zero", "void", "blank"],
            "error": ["error", "exception", "fail", "invalid", "bad", "wrong", "raise"],
            "edge": ["edge", "boundary", "limit", "extreme", "corner", "min", "max"],
        }

    def score(self) -> float:
        """
        Compute a composite diversity score between 0 and 1.
        Higher is more diverse.
        """
        modules_tested = self._count_unique_modules()
        size_distribution = self._compute_size_distribution()
        edge_case_count = self._count_edge_case_tests()

        # Normalize each component to [0, 1]
        module_score = self._normalize_module_count(modules_tested)
        distribution_score = self._normalize_distribution(size_distribution)
        edge_score = self._normalize_edge_count(edge_case_count)

        # Weighted combination (weights sum to 1)
        weights = (0.4, 0.3, 0.3)
        total = (
            weights[0] * module_score +
            weights[1] * distribution_score +
            weights[2] * edge_score
        )
        return round(total, 4)

    def _count_unique_modules(self) -> int:
        """Count distinct Python modules (files) in the test directory."""
        if not os.path.isdir(self.test_dir):
            return 0
        modules = set()
        for root, dirs, files in os.walk(self.test_dir):
            for f in files:
                if f.endswith(".py") and f.startswith("test_"):
                    # Use relative path as module identifier
                    rel_path = os.path.relpath(os.path.join(root, f), self.test_dir)
                    modules.add(rel_path)
        return len(modules)

    def _compute_size_distribution(self) -> List[int]:
        """
        For each test file, count the number of test functions (def test_*).
        Returns list of counts.
        """
        sizes = []
        if not os.path.isdir(self.test_dir):
            return sizes
        for root, dirs, files in os.walk(self.test_dir):
            for f in files:
                if f.endswith(".py") and f.startswith("test_"):
                    filepath = os.path.join(root, f)
                    try:
                        with open(filepath, "r", encoding="utf-8") as fh:
                            tree = ast.parse(fh.read(), filename=filepath)
                        count = sum(
                            1 for node in ast.walk(tree)
                            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
                        )
                        sizes.append(count)
                    except (SyntaxError, UnicodeDecodeError, IOError):
                        continue
        return sizes

    def _count_edge_case_tests(self) -> int:
        """
        Count test functions that appear to test edge cases based on name analysis.
        Looks for keywords like empty, error, edge, boundary, etc.
        """
        count = 0
        if not os.path.isdir(self.test_dir):
            return count
        for root, dirs, files in os.walk(self.test_dir):
            for f in files:
                if f.endswith(".py") and f.startswith("test_"):
                    filepath = os.path.join(root, f)
                    try:
                        with open(filepath, "r", encoding="utf-8") as fh:
                            tree = ast.parse(fh.read(), filename=filepath)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                                name_lower = node.name.lower()
                                for category, keywords in self.edge_case_keywords.items():
                                    for kw in keywords:
                                        if kw in name_lower:
                                            count += 1
                                            break  # Count each test only once
                    except (SyntaxError, UnicodeDecodeError, IOError):
                        continue
        return count

    def _normalize_module_count(self, count: int) -> float:
        """Normalize module count to [0, 1] using a saturating function."""
        # Assume 20+ modules is excellent
        return min(1.0, count / 20.0)

    def _normalize_distribution(self, sizes: List[int]) -> float:
        """
        Score how evenly distributed test sizes are.
        Uses coefficient of variation (CV) – lower CV is better.
        Returns 1 for perfect uniformity, 0 for extreme imbalance.
        """
        if not sizes:
            return 0.0
        if len(sizes) == 1:
            return 1.0  # Single file is trivially uniform
        mean = sum(sizes) / len(sizes)
        if mean == 0:
            return 0.0
        variance = sum((s - mean) ** 2 for s in sizes) / len(sizes)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean
        # CV of 0 is perfect; CV >= 1 is poor
        return max(0.0, 1.0 - cv)

    def _normalize_edge_count(self, count: int) -> float:
        """Normalize edge case count to [0, 1]."""
        # Assume 10+ edge tests is excellent
        return min(1.0, count / 10.0)

    def detailed_report(self) -> Dict[str, object]:
        """
        Return a dictionary with detailed scoring components for debugging.
        """
        modules_tested = self._count_unique_modules()
        size_distribution = self._compute_size_distribution()
        edge_case_count = self._count_edge_case_tests()

        return {
            "unique_modules": modules_tested,
            "module_score": self._normalize_module_count(modules_tested),
            "test_sizes": size_distribution,
            "size_distribution_score": self._normalize_distribution(size_distribution),
            "edge_case_tests": edge_case_count,
            "edge_case_score": self._normalize_edge_count(edge_case_count),
            "composite_score": self.score(),
        }


def score_test_suite(test_dir: str = "tests") -> float:
    """
    Convenience function to quickly score a test suite.
    """
    scorer = TestDiversityScorer(test_dir)
    return scorer.score()


def compare_suites(suite_a: str, suite_b: str) -> Dict[str, float]:
    """
    Compare diversity scores of two test suites.
    Returns a dict with individual scores and the difference.
    """
    score_a = score_test_suite(suite_a)
    score_b = score_test_suite(suite_b)
    return {
        "suite_a_score": score_a,
        "suite_b_score": score_b,
        "difference": score_a - score_b,
    }