import unittest
from unittest.mock import Mock, patch
import json
from datetime import datetime
from typing import Dict, List, Any

# Assuming the module structure; adjust imports as needed
from src.health_audit import (
    score_capability,
    identify_bottom_10_percent,
    detect_duplicates,
    merge_capabilities,
    prune_capabilities,
    Capability,
    Dependency
)

class TestHealthAudit(unittest.TestCase):
    """Unit tests for health audit functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.capabilities = [
            Capability(
                id="cap_1",
                name="Implement a canonical schema alignment layer",
                description="Schema alignment for data integration",
                score=85,
                dependencies=[Dependency(id="dep_1", name="Data integration framework")]
            ),
            Capability(
                id="cap_2",
                name="Implement a canonical schema alignment layer",
                description="Schema alignment for data integration",
                score=92,
                dependencies=[Dependency(id="dep_2", name="Data integration framework")]
            ),
            Capability(
                id="cap_3",
                name="Data validation pipeline",
                description="Validate incoming data",
                score=45,
                dependencies=[Dependency(id="dep_3", name="Validation rules engine")]
            ),
            Capability(
                id="cap_4",
                name="API gateway configuration",
                description="Configure API endpoints",
                score=78,
                dependencies=[Dependency(id="dep_4", name="API management platform")]
            ),
            Capability(
                id="cap_5",
                name="Monitoring and alerting",
                description="System monitoring setup",
                score=30,
                dependencies=[Dependency(id="dep_5", name="Monitoring infrastructure")]
            ),
        ]

    def test_scoring_logic_with_known_inputs(self):
        """Test scoring logic produces expected scores for known inputs."""
        # Test with various input combinations
        test_cases = [
            {
                "capability": Capability(
                    id="test_1",
                    name="Test capability",
                    description="Test",
                    dependencies=[Dependency(id="dep_test", name="Test dep")],
                    complexity=3,
                    coverage=0.8,
                    maturity=0.7
                ),
                "expected_score": 85  # Adjust based on actual scoring formula
            },
            {
                "capability": Capability(
                    id="test_2",
                    name="Test capability 2",
                    description="Test 2",
                    dependencies=[Dependency(id="dep_test2", name="Test dep 2")],
                    complexity=5,
                    coverage=0.4,
                    maturity=0.3
                ),
                "expected_score": 45  # Adjust based on actual scoring formula
            }
        ]

        for test_case in test_cases:
            with self.subTest(capability_id=test_case["capability"].id):
                result = score_capability(test_case["capability"])
                self.assertEqual(result, test_case["expected_score"])

    def test_bottom_10_percent_identification(self):
        """Test identification of bottom 10% capabilities with 20 capabilities."""
        # Create 20 capabilities with varying scores
        capabilities_20 = []
        for i in range(20):
            capabilities_20.append(
                Capability(
                    id=f"cap_{i}",
                    name=f"Capability {i}",
                    description=f"Description {i}",
                    score=10 + (i * 5)  # Scores from 10 to 105
                )
            )

        result = identify_bottom_10_percent(capabilities_20)
        
        # Should identify bottom 10% (2 capabilities out of 20)
        self.assertEqual(len(result), 2)
        
        # The bottom 2 should have the lowest scores
        self.assertEqual(result[0].id, "cap_0")
        self.assertEqual(result[1].id, "cap_1")
        
        # Verify scores are in ascending order
        for i in range(len(result) - 1):
            self.assertLessEqual(result[i].score, result[i + 1].score)

    def test_duplicate_detection_same_prefix(self):
        """Test detection of duplicates with same prefix 'Implement a canonical schema alignment layer'."""
        duplicates = detect_duplicates(self.capabilities)
        
        # Should detect cap_1 and cap_2 as duplicates
        duplicate_ids = [dup.id for dup in duplicates]
        self.assertIn("cap_1", duplicate_ids)
        self.assertIn("cap_2", duplicate_ids)
        
        # Should not include non-duplicates
        self.assertNotIn("cap_3", duplicate_ids)
        self.assertNotIn("cap_4", duplicate_ids)
        self.assertNotIn("cap_5", duplicate_ids)

    def test_merge_preserves_functionality(self):
        """Test that merging capabilities preserves functionality."""
        # Create capabilities to merge
        cap_a = Capability(
            id="merge_a",
            name="Implement a canonical schema alignment layer",
            description="Schema alignment for data integration",
            score=85,
            dependencies=[
                Dependency(id="dep_1", name="Data integration framework"),
                Dependency(id="dep_2", name="Schema registry")
            ]
        )
        
        cap_b = Capability(
            id="merge_b",
            name="Implement a canonical schema alignment layer",
            description="Schema alignment for data integration",
            score=92,
            dependencies=[
                Dependency(id="dep_1", name="Data integration framework"),
                Dependency(id="dep_3", name="Data transformation engine")
            ]
        )
        
        merged = merge_capabilities(cap_a, cap_b)
        
        # Verify merged capability preserves functionality
        self.assertEqual(merged.name, "Implement a canonical schema alignment layer")
        self.assertIn("schema alignment", merged.description.lower())
        
        # Verify dependencies are merged without duplicates
        dependency_names = [dep.name for dep in merged.dependencies]
        self.assertIn("Data integration framework", dependency_names)
        self.assertIn("Schema registry", dependency_names)
        self.assertIn("Data transformation engine", dependency_names)
        
        # Verify no duplicate dependencies
        self.assertEqual(len(merged.dependencies), 3)
        
        # Verify score is aggregated (e.g., average or max)
        self.assertGreaterEqual(merged.score, 85)
        self.assertLessEqual(merged.score, 92)

    def test_pruning_does_not_remove_critical_dependencies(self):
        """Test that pruning doesn't remove critical dependencies."""
        # Create capabilities with critical dependencies
        capabilities_with_critical = [
            Capability(
                id="critical_cap_1",
                name="Core system",
                description="Core system functionality",
                score=90,
                dependencies=[
                    Dependency(id="dep_critical", name="Critical dependency", critical=True),
                    Dependency(id="dep_normal", name="Normal dependency", critical=False)
                ]
            ),
            Capability(
                id="critical_cap_2",
                name="Secondary system",
                description="Secondary system functionality",
                score=60,
                dependencies=[
                    Dependency(id="dep_critical", name="Critical dependency", critical=True),
                    Dependency(id="dep_optional", name="Optional dependency", critical=False)
                ]
            )
        ]
        
        # Prune with threshold that would remove some normal dependencies
        pruned = prune_capabilities(capabilities_with_critical, threshold=0.5)
        
        # Verify critical dependencies are preserved
        for cap in pruned:
            critical_deps = [dep for dep in cap.dependencies if dep.critical]
            self.assertGreater(len(critical_deps), 0, 
                             f"Critical dependencies should not be removed from {cap.id}")
        
        # Verify the critical dependency is still present
        all_dep_names = [dep.name for cap in pruned for dep in cap.dependencies]
        self.assertIn("Critical dependency", all_dep_names)

    def test_merge_with_empty_dependencies(self):
        """Test merge functionality when one capability has no dependencies."""
        cap_with_deps = Capability(
            id="with_deps",
            name="Test capability",
            description="Test",
            score=80,
            dependencies=[Dependency(id="dep_1", name="Test dep")]
        )
        
        cap_without_deps = Capability(
            id="without_deps",
            name="Test capability",
            description="Test",
            score=85,
            dependencies=[]
        )
        
        merged = merge_capabilities(cap_with_deps, cap_without_deps)
        self.assertEqual(len(merged.dependencies), 1)
        self.assertEqual(merged.dependencies[0].name, "Test dep")

    def test_pruning_with_no_critical_dependencies(self):
        """Test pruning when no dependencies are marked as critical."""
        capabilities = [
            Capability(
                id="cap_1",
                name="Test capability",
                description="Test",
                score=70,
                dependencies=[
                    Dependency(id="dep_1", name="Dep 1", critical=False),
                    Dependency(id="dep_2", name="Dep 2", critical=False)
                ]
            )
        ]
        
        # Prune with high threshold
        pruned = prune_capabilities(capabilities, threshold=0.8)
        
        # Should still preserve some dependencies based on other criteria
        self.assertGreater(len(pruned[0].dependencies), 0)

if __name__ == '__main__':
    unittest.main()