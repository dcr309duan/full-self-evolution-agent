"""
core/test_suite_evolution.py

Tracks the diversity of the test suite over time.
Maintains a registry of test types, detects missing types, and generates templates.
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import os

# Registry of all recognized test types with metadata
TEST_TYPE_REGISTRY: Dict[str, Dict] = {
    "unit": {
        "description": "Tests individual functions/methods in isolation",
        "priority": 1,
        "template_file": "test_unit_{name}.py",
        "template_content": """\"\"\"
Unit tests for {name}
\"\"\"
import pytest

class Test{Name}:
    def test_{name}_basic(self):
        \"\"\"Basic unit test for {name}\"\"\"
        assert True

    def test_{name}_edge_cases(self):
        \"\"\"Edge case tests for {name}\"\"\"
        assert True
"""
    },
    "integration": {
        "description": "Tests interactions between multiple components",
        "priority": 2,
        "template_file": "test_integration_{name}.py",
        "template_content": """\"\"\"
Integration tests for {name}
\"\"\"
import pytest

class Test{Name}Integration:
    def test_{name}_integration_basic(self):
        \"\"\"Basic integration test for {name}\"\"\"
        assert True

    def test_{name}_integration_flow(self):
        \"\"\"Full integration flow test for {name}\"\"\"
        assert True
"""
    },
    "performance": {
        "description": "Tests performance characteristics and benchmarks",
        "priority": 3,
        "template_file": "test_perf_{name}.py",
        "template_content": """\"\"\"
Performance tests for {name}
\"\"\"
import pytest
import time

class Test{Name}Performance:
    def test_{name}_response_time(self):
        \"\"\"Measure response time of {name}\"\"\"
        start = time.time()
        # TODO: Add actual performance test logic
        elapsed = time.time() - start
        assert elapsed < 1.0, f"Performance threshold exceeded: {elapsed:.3f}s"

    def test_{name}_throughput(self):
        \"\"\"Measure throughput of {name}\"\"\"
        # TODO: Add actual throughput measurement
        assert True
"""
    },
    "stress": {
        "description": "Tests system behavior under extreme conditions",
        "priority": 4,
        "template_file": "test_stress_{name}.py",
        "template_content": """\"\"\"
Stress tests for {name}
\"\"\"
import pytest

class Test{Name}Stress:
    def test_{name}_high_load(self):
        \"\"\"Test {name} under high load conditions\"\"\"
        # TODO: Implement high load stress test
        assert True

    def test_{name}_concurrent_access(self):
        \"\"\"Test {name} with concurrent access patterns\"\"\"
        # TODO: Implement concurrent access stress test
        assert True
"""
    },
    "mutation": {
        "description": "Tests that verify mutation testing coverage",
        "priority": 5,
        "template_file": "test_mutation_{name}.py",
        "template_content": """\"\"\"
Mutation tests for {name}
\"\"\"
import pytest

class Test{Name}Mutation:
    def test_{name}_mutation_coverage(self):
        \"\"\"Verify mutation coverage for {name}\"\"\"
        # TODO: Implement mutation testing logic
        assert True

    def test_{name}_mutation_survival(self):
        \"\"\"Check mutation survival rate for {name}\"\"\"
        # TODO: Implement mutation survival analysis
        assert True
"""
    },
    "fuzz": {
        "description": "Tests with random/fuzzed inputs",
        "priority": 6,
        "template_file": "test_fuzz_{name}.py",
        "template_content": """\"\"\"
Fuzz tests for {name}
\"\"\"
import pytest
import random

class Test{Name}Fuzz:
    def test_{name}_random_inputs(self):
        \"\"\"Test {name} with random inputs\"\"\"
        for _ in range(10):
            # TODO: Generate random input for {name}
            random_input = random.randint(0, 1000)
            assert True

    def test_{name}_boundary_values(self):
        \"\"\"Test {name} with boundary values\"\"\"
        # TODO: Add boundary value tests
        assert True
"""
    }
}

# Default test types that should always be present
DEFAULT_TEST_TYPES: Set[str] = {"unit", "integration", "performance"}


@dataclass
class TestSuiteSnapshot:
    """Represents a snapshot of the test suite at a point in time."""
    timestamp: datetime = field(default_factory=datetime.now)
    test_types_present: Set[str] = field(default_factory=set)
    total_test_count: int = 0
    missing_types: Set[str] = field(default_factory=set)
    diversity_score: float = 0.0
    snapshot_hash: str = ""


class TestSuiteEvolution:
    """
    Tracks the evolution and diversity of the test suite.
    Maintains a history of test type presence and generates templates for missing types.
    """

    def __init__(self, history_file: Optional[str] = None):
        self.history: List[TestSuiteSnapshot] = []
        self.history_file = history_file or "test_suite_evolution_history.json"
        self._load_history()

    def _load_history(self) -> None:
        """Load history from file if it exists."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    for entry in data:
                        snapshot = TestSuiteSnapshot(
                            timestamp=datetime.fromisoformat(entry['timestamp']),
                            test_types_present=set(entry['test_types_present']),
                            total_test_count=entry['total_test_count'],
                            missing_types=set(entry['missing_types']),
                            diversity_score=entry['diversity_score'],
                            snapshot_hash=entry['snapshot_hash']
                        )
                        self.history.append(snapshot)
            except (json.JSONDecodeError, KeyError, ValueError):
                self.history = []

    def _save_history(self) -> None:
        """Save history to file."""
        data = []
        for snapshot in self.history:
            data.append({
                'timestamp': snapshot.timestamp.isoformat(),
                'test_types_present': list(snapshot.test_types_present),
                'total_test_count': snapshot.total_test_count,
                'missing_types': list(snapshot.missing_types),
                'diversity_score': snapshot.diversity_score,
                'snapshot_hash': snapshot.snapshot_hash
            })
        with open(self.history_file, 'w') as f:
            json.dump(data, f, indent=2)

    def detect_missing_types(self, present_types: Set[str]) -> Set[str]:
        """
        Detect which test types are missing from the current test suite.
        
        Args:
            present_types: Set of test type names currently present
            
        Returns:
            Set of missing test type names
        """
        all_types = set(TEST_TYPE_REGISTRY.keys())
        missing = all_types - present_types
        return missing

    def calculate_diversity_score(self, present_types: Set[str]) -> float:
        """
        Calculate a diversity score based on how many test types are present.
        
        Args:
            present_types: Set of test type names currently present
            
        Returns:
            Float between 0.0 and 1.0 representing diversity
        """
        if not TEST_TYPE_REGISTRY:
            return 0.0
        return len(present_types) / len(TEST_TYPE_REGISTRY)

    def generate_template(self, test_type: str, name: str) -> Optional[str]:
        """
        Generate a minimal template for a given test type.
        
        Args:
            test_type: The type of test (e.g., 'unit', 'integration')
            name: The name of the component/module being tested
            
        Returns:
            Template content as string, or None if test type not found
        """
        if test_type not in TEST_TYPE_REGISTRY:
            return None
        
        template_info = TEST_TYPE_REGISTRY[test_type]
        template = template_info['template_content']
        
        # Format the template with the provided name
        formatted_name = name.replace('_', ' ').title().replace(' ', '')
        return template.format(name=name, Name=formatted_name)

    def take_snapshot(self, present_types: Set[str], total_test_count: int) -> TestSuiteSnapshot:
        """
        Take a snapshot of the current test suite state.
        
        Args:
            present_types: Set of test type names currently present
            total_test_count: Total number of tests in the suite
            
        Returns:
            TestSuiteSnapshot object
        """
        missing_types = self.detect_missing_types(present_types)
        diversity_score = self.calculate_diversity_score(present_types)
        
        # Create a hash for deduplication
        snapshot_data = f"{present_types}|{total_test_count}|{datetime.now().isoformat()}"
        snapshot_hash = hashlib.sha256(snapshot_data.encode()).hexdigest()[:12]
        
        snapshot = TestSuiteSnapshot(
            test_types_present=present_types,
            total_test_count=total_test_count,
            missing_types=missing_types,
            diversity_score=diversity_score,
            snapshot_hash=snapshot_hash
        )
        
        self.history.append(snapshot)
        self._save_history()
        
        return snapshot

    def get_evolution_report(self) -> Dict:
        """
        Generate a report on the evolution of the test suite.
        
        Returns:
            Dictionary with evolution statistics
        """
        if not self.history:
            return {
                "total_snapshots": 0,
                "current_diversity": 0.0,
                "diversity_trend": "no_data",
                "persistently_missing_types": [],
                "recommendations": ["Start tracking test suite evolution"]
            }
        
        current = self.history[-1]
        
        # Calculate diversity trend
        if len(self.history) >= 2:
            prev_diversity = self.history[-2].diversity_score
            if current.diversity_score > prev_diversity:
                trend = "improving"
            elif current.diversity_score < prev_diversity:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "baseline_established"
        
        # Find persistently missing types
        all_missing_counts: Dict[str, int] = {}
        for snapshot in self.history:
            for missing_type in snapshot.missing_types:
                all_missing_counts[missing_type] = all_missing_counts.get(missing_type, 0) + 1
        
        persistently_missing = [
            t for t, count in all_missing_counts.items()
            if count == len(self.history)
        ]
        
        # Generate recommendations
        recommendations = []
        if current.missing_types:
            for missing in sorted(current.missing_types, key=lambda x: TEST_TYPE_REGISTRY.get(x, {}).get('priority', 99)):
                recommendations.append(
                    f"Add {missing} tests (priority {TEST_TYPE_REGISTRY.get(missing, {}).get('priority', 'unknown')})"
                )
        
        if current.diversity_score < 0.5:
            recommendations.append("Critical: Test suite diversity is below 50%")
        
        return {
            "total_snapshots": len(self.history),
            "current_diversity": current.diversity_score,
            "diversity_trend": trend,
            "persistently_missing_types": persistently_missing,
            "recommendations": recommendations
        }

    def get_available_test_types(self) -> List[str]:
        """Return list of all recognized test types."""
        return list(TEST_TYPE_REGISTRY.keys())

    def get_test_type_info(self, test_type: str) -> Optional[Dict]:
        """Get metadata for a specific test type."""
        return TEST_TYPE_REGISTRY.get(test_type)


# Convenience functions for external use
def create_evolution_tracker(history_file: Optional[str] = None) -> TestSuiteEvolution:
    """Create a new TestSuiteEvolution instance."""
    return TestSuiteEvolution(history_file)


def get_default_test_types() -> Set[str]:
    """Return the set of default test types that should always be present."""
    return DEFAULT_TEST_TYPES.copy()


def get_all_test_types() -> List[str]:
    """Return all recognized test types."""
    return list(TEST_TYPE_REGISTRY.keys())