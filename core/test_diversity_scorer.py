import os
import ast
import math
from collections import Counter
from typing import Dict, List, Tuple, Optional, Set

class TestDiversityScorer:
    """
    Scores a test suite's diversity based on:
    1. Number of unique modules tested
    2. Distribution of test sizes (number of test functions per file)
    3. Presence of edge case tests (empty input, error handling)
    4. Assertion type diversity
    5. Dead zone identification
    """

    def __init__(self, test_dir: str = "tests"):
        self.test_dir = test_dir
        self.edge_case_keywords = {
            "empty": ["empty", "null", "none", "zero", "void", "blank"],
            "error": ["error", "exception", "fail", "invalid", "bad", "wrong", "raise"],
            "edge": ["edge", "boundary", "limit", "extreme", "corner", "min", "max"],
        }
        self.assertion_types = {
            "assertEqual", "assertNotEqual", "assertTrue", "assertFalse",
            "assertIs", "assertIsNot", "assertIsNone", "assertIsNotNone",
            "assertIn", "assertNotIn", "assertIsInstance", "assertNotIsInstance",
            "assertRaises", "assertRaisesRegex", "assertWarns", "assertWarnsRegex",
            "assertLogs", "assertAlmostEqual", "assertNotAlmostEqual",
            "assertGreater", "assertGreaterEqual", "assertLess", "assertLessEqual",
            "assertRegex", "assertNotRegex", "assertCountEqual",
            "assertMultiLineEqual", "assertSequenceEqual", "assertListEqual",
            "assertTupleEqual", "assertSetEqual", "assertDictEqual",
            "fail", "skip", "skipIf", "skipUnless", "expectedFailure"
        }

    def score(self) -> float:
        """
        Compute a composite diversity score between 0 and 1.
        Higher is more diverse.
        """
        modules_tested = self._count_unique_modules()
        size_distribution = self._compute_size_distribution()
        edge_case_count = self._count_edge_case_tests()
        assertion_diversity = self._compute_assertion_diversity()
        dead_zones = self._identify_dead_zones()

        # Normalize each component to [0, 1]
        module_score = self._normalize_module_count(modules_tested)
        distribution_score = self._normalize_distribution(size_distribution)
        edge_score = self._normalize_edge_count(edge_case_count)
        assertion_score = self._normalize_assertion_diversity(assertion_diversity)
        dead_zone_penalty = self._compute_dead_zone_penalty(dead_zones)

        # Weighted combination (weights sum to 1)
        weights = (0.25, 0.2, 0.2, 0.25, 0.1)
        total = (
            weights[0] * module_score +
            weights[1] * distribution_score +
            weights[2] * edge_score +
            weights[3] * assertion_score -
            weights[4] * dead_zone_penalty
        )
        return round(max(0.0, min(1.0, total)), 4)

    def _count_unique_modules(self) -> int:
        """Count distinct Python modules (files) in the test directory."""
        if not os.path.isdir(self.test_dir):
            return 0
        modules = set()
        for root, dirs, files in os.walk(self.test_dir):
            for f in files:
                if f.endswith(".py") and f.startswith("test_"):
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
                                            break
                    except (SyntaxError, UnicodeDecodeError, IOError):
                        continue
        return count

    def _extract_assertion_types(self) -> Dict[str, int]:
        """
        Parse all test files and extract assertion types used.
        Returns a Counter-like dict mapping assertion type to count.
        """
        assertion_counts = Counter()
        if not os.path.isdir(self.test_dir):
            return dict(assertion_counts)
        
        for root, dirs, files in os.walk(self.test_dir):
            for f in files:
                if f.endswith(".py") and f.startswith("test_"):
                    filepath = os.path.join(root, f)
                    try:
                        with open(filepath, "r", encoding="utf-8") as fh:
                            tree = ast.parse(fh.read(), filename=filepath)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Call):
                                if isinstance(node.func, ast.Attribute):
                                    method_name = node.func.attr
                                    if method_name in self.assertion_types:
                                        assertion_counts[method_name] += 1
                                elif isinstance(node.func, ast.Name):
                                    func_name = node.func.id
                                    if func_name in self.assertion_types:
                                        assertion_counts[func_name] += 1
                    except (SyntaxError, UnicodeDecodeError, IOError):
                        continue
        return dict(assertion_counts)

    def _compute_assertion_diversity(self) -> float:
        """
        Compute a diversity score based on the number of unique assertion patterns.
        Returns a value between 0 and 1.
        """
        assertion_counts = self._extract_assertion_types()
        if not assertion_counts:
            return 0.0
        
        total_assertions = sum(assertion_counts.values())
        unique_types = len(assertion_counts)
        
        # Normalize by total possible assertion types
        type_coverage = unique_types / len(self.assertion_types)
        
        # Compute Shannon entropy for distribution evenness
        if total_assertions > 0:
            entropy = 0.0
            for count in assertion_counts.values():
                prob = count / total_assertions
                if prob > 0:
                    entropy -= prob * math.log2(prob)
            max_entropy = math.log2(unique_types) if unique_types > 0 else 1
            evenness = entropy / max_entropy if max_entropy > 0 else 0
        else:
            evenness = 0.0
        
        # Combine coverage and evenness
        return (type_coverage * 0.6 + evenness * 0.4)

    def _identify_dead_zones(self) -> Dict[str, bool]:
        """
        Identify 'dead zones' where no tests exist for certain assertion types.
        Returns a dict mapping assertion type to whether it's a dead zone (True if missing).
        """
        assertion_counts = self._extract_assertion_types()
        dead_zones = {}
        for assertion_type in self.assertion_types:
            dead_zones[assertion_type] = assertion_type not in assertion_counts
        return dead_zones

    def _normalize_module_count(self, count: int) -> float:
        """Normalize module count to [0, 1] using a saturating function."""
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
            return 1.0
        mean = sum(sizes) / len(sizes)
        if mean == 0:
            return 0.0
        variance = sum((s - mean) ** 2 for s in sizes) / len(sizes)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean
        return max(0.0, 1.0 - cv)

    def _normalize_edge_count(self, count: int) -> float:
        """Normalize edge case count to [0, 1]."""
        return min(1.0, count / 10.0)

    def _normalize_assertion_diversity(self, diversity: float) -> float:
        """Normalize assertion diversity score to [0, 1]."""
        return min(1.0, diversity)

    def _compute_dead_zone_penalty(self, dead_zones: Dict[str, bool]) -> float:
        """
        Compute penalty based on number of dead zones.
        Returns a value between 0 and 1.
        """
        if not dead_zones:
            return 0.0
        dead_zone_count = sum(1 for is_dead in dead_zones.values() if is_dead)
        total_types = len(dead_zones)
        return dead_zone_count / total_types if total_types > 0 else 0.0

    def detailed_report(self) -> Dict[str, object]:
        """
        Return a dictionary with detailed scoring components for debugging.
        """
        modules_tested = self._count_unique_modules()
        size_distribution = self._compute_size_distribution()
        edge_case_count = self._count_edge_case_tests()
        assertion_diversity = self._compute_assertion_diversity()
        dead_zones = self._identify_dead_zones()
        assertion_counts = self._extract_assertion_types()

        return {
            "unique_modules": modules_tested,
            "module_score": self._normalize_module_count(modules_tested),
            "test_sizes": size_distribution,
            "size_distribution_score": self._normalize_distribution(size_distribution),
            "edge_case_tests": edge_case_count,
            "edge_case_score": self._normalize_edge_count(edge_case_count),
            "assertion_diversity_score": assertion_diversity,
            "assertion_counts": assertion_counts,
            "dead_zones": dead_zones,
            "dead_zone_penalty": self._compute_dead_zone_penalty(dead_zones),
            "composite_score": self.score(),
        }

    def get_guidance_for_ecology_engine(self) -> Dict[str, object]:
        """
        Provide data to the ecology engine to guide benchmark generation
        toward under-tested areas.
        """
        dead_zones = self._identify_dead_zones()
        assertion_counts = self._extract_assertion_types()
        
        # Identify under-tested assertion types (those with low usage)
        under_tested = {}
        for assertion_type in self.assertion_types:
            count = assertion_counts.get(assertion_type, 0)
            if count < 2:  # Threshold for under-tested
                under_tested[assertion_type] = count
        
        return {
            "dead_zones": [at for at, is_dead in dead_zones.items() if is_dead],
            "under_tested_assertions": under_tested,
            "assertion_diversity_score": self._compute_assertion_diversity(),
            "recommended_focus": list(under_tested.keys()) if under_tested else list(dead_zones.keys())[:5]
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