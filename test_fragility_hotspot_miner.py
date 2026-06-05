import unittest
from collections import Counter
from fragility_hotspot_miner import FragilityHotspotMiner

class TestFragilityHotspotMiner(unittest.TestCase):
    """Test suite for FragilityHotspotMiner class."""

    def setUp(self):
        """Initialize the miner instance for each test."""
        self.miner = FragilityHotspotMiner()

    def test_repeated_module_pairs(self):
        """Test 1: Simulated failure logs with repeated module pairs."""
        failure_logs = [
            "ModuleA:ModuleB failed",
            "ModuleA:ModuleB failed",
            "ModuleC:ModuleD failed",
            "ModuleA:ModuleB failed",
            "ModuleE:ModuleF failed"
        ]
        self.miner.process_failure_logs(failure_logs)
        expected_pairs = {("ModuleA", "ModuleB"): 3, ("ModuleC", "ModuleD"): 1, ("ModuleE", "ModuleF"): 1}
        self.assertEqual(self.miner.pair_counts, expected_pairs)

    def test_pair_counting_logic(self):
        """Test 2: Verify pair counting logic with various inputs."""
        failure_logs = [
            "X:Y failed",
            "X:Y failed",
            "X:Z failed",
            "Y:Z failed",
            "X:Y failed"
        ]
        self.miner.process_failure_logs(failure_logs)
        self.assertEqual(self.miner.pair_counts[("X", "Y")], 3)
        self.assertEqual(self.miner.pair_counts[("X", "Z")], 1)
        self.assertEqual(self.miner.pair_counts[("Y", "Z")], 1)

    def test_threshold_detection(self):
        """Test 3: Threshold detection (>3 occurrences)."""
        failure_logs = [
            "A:B failed",
            "A:B failed",
            "A:B failed",
            "A:B failed",  # 4th occurrence, should exceed threshold
            "C:D failed",
            "C:D failed",
            "C:D failed"   # 3 occurrences, should not exceed threshold
        ]
        self.miner.process_failure_logs(failure_logs)
        hotspots = self.miner.get_hotspots(threshold=3)
        self.assertIn(("A", "B"), hotspots)
        self.assertNotIn(("C", "D"), hotspots)

    def test_goal_generation_format(self):
        """Test 4: Verify goal generation format."""
        failure_logs = [
            "ModuleX:ModuleY failed",
            "ModuleX:ModuleY failed",
            "ModuleX:ModuleY failed",
            "ModuleX:ModuleY failed",
            "ModuleX:ModuleY failed"
        ]
        self.miner.process_failure_logs(failure_logs)
        goals = self.miner.generate_goals(threshold=3)
        expected_goal = "Investigate fragility hotspot between ModuleX and ModuleY (5 occurrences)"
        self.assertIn(expected_goal, goals)
        self.assertEqual(len(goals), 1)

    def test_single_failures(self):
        """Test 5a: Edge case - single failures (no pairs)."""
        failure_logs = [
            "ModuleA failed",
            "ModuleB failed",
            "ModuleC failed"
        ]
        self.miner.process_failure_logs(failure_logs)
        self.assertEqual(len(self.miner.pair_counts), 0)

    def test_no_pairs(self):
        """Test 5b: Edge case - no pairs at all."""
        failure_logs = []
        self.miner.process_failure_logs(failure_logs)
        self.assertEqual(len(self.miner.pair_counts), 0)
        self.assertEqual(self.miner.generate_goals(threshold=3), [])

    def test_all_unique_pairs(self):
        """Test 5c: Edge case - all unique pairs (none exceed threshold)."""
        failure_logs = [
            "A:B failed",
            "C:D failed",
            "E:F failed",
            "G:H failed"
        ]
        self.miner.process_failure_logs(failure_logs)
        hotspots = self.miner.get_hotspots(threshold=3)
        self.assertEqual(len(hotspots), 0)


if __name__ == '__main__':
    unittest.main()