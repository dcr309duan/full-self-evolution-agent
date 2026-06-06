import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the core directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))

from capability_deduplicator import CapabilityDeduplicator

class TestCapabilityDeduplicator(unittest.TestCase):
    def setUp(self):
        """Set up a fresh deduplicator for each test."""
        self.deduplicator = CapabilityDeduplicator()

    def test_exact_duplicate_detection(self):
        """Test that exact duplicate capabilities are detected."""
        cap1 = "The ability to fly at supersonic speeds"
        cap2 = "The ability to fly at supersonic speeds"
        
        result1 = self.deduplicator.check_duplicate(cap1)
        result2 = self.deduplicator.check_duplicate(cap2)
        
        # First should be unique
        self.assertFalse(result1.is_duplicate)
        self.assertEqual(result1.failure_count, 0)
        
        # Second should be detected as duplicate
        self.assertTrue(result2.is_duplicate)
        self.assertEqual(result2.failure_count, 1)

    def test_near_duplicate_detection(self):
        """Test that near-duplicates (same prefix, different suffix) are detected."""
        cap1 = "Enhanced strength: level 1"
        cap2 = "Enhanced strength: level 2"
        cap3 = "Enhanced strength: level 3"
        
        result1 = self.deduplicator.check_duplicate(cap1)
        result2 = self.deduplicator.check_duplicate(cap2)
        result3 = self.deduplicator.check_duplicate(cap3)
        
        # First should be unique
        self.assertFalse(result1.is_duplicate)
        
        # Second and third should be detected as near-duplicates
        self.assertTrue(result2.is_duplicate)
        self.assertTrue(result3.is_duplicate)

    def test_failure_count_tracking(self):
        """Test that failure counts are tracked correctly."""
        cap = "Telepathy range: 100 meters"
        
        # Submit the same capability multiple times
        for i in range(3):
            result = self.deduplicator.check_duplicate(cap)
            if i == 0:
                self.assertFalse(result.is_duplicate)
                self.assertEqual(result.failure_count, 0)
            else:
                self.assertTrue(result.is_duplicate)
                self.assertEqual(result.failure_count, i)

    def test_archiving_after_three_failures(self):
        """Test that capabilities are archived after more than 3 failures."""
        cap = "Invisibility: duration 30 minutes"
        
        # Submit 4 times to trigger archiving
        for i in range(4):
            result = self.deduplicator.check_duplicate(cap)
            
            if i == 0:
                self.assertFalse(result.is_duplicate)
                self.assertFalse(result.is_archived)
            elif i <= 3:
                self.assertTrue(result.is_duplicate)
                self.assertFalse(result.is_archived)
            else:
                self.assertTrue(result.is_duplicate)
                self.assertTrue(result.is_archived)
        
        # Verify it's in the archive
        self.assertIn(cap, self.deduplicator.archived_capabilities)

    def test_unique_capabilities_preserved(self):
        """Test that unique capabilities are not marked as duplicates."""
        unique_caps = [
            "Super strength",
            "Flight capability",
            "Teleportation",
            "Time manipulation",
            "Invisibility"
        ]
        
        for cap in unique_caps:
            result = self.deduplicator.check_duplicate(cap)
            self.assertFalse(result.is_duplicate, f"Capability '{cap}' should be unique")
            self.assertEqual(result.failure_count, 0)

    def test_mixed_duplicates_and_uniques(self):
        """Test that duplicates and uniques are handled correctly together."""
        caps = [
            ("Unique power A", False),
            ("Duplicate power X", False),
            ("Duplicate power X", True),
            ("Unique power B", False),
            ("Duplicate power Y", False),
            ("Duplicate power Y", True),
            ("Duplicate power Y", True),
        ]
        
        for cap, expected_duplicate in caps:
            result = self.deduplicator.check_duplicate(cap)
            self.assertEqual(result.is_duplicate, expected_duplicate,
                           f"Expected duplicate={expected_duplicate} for '{cap}'")

    def test_empty_capability_handling(self):
        """Test that empty capabilities are handled gracefully."""
        empty_cap = ""
        
        result = self.deduplicator.check_duplicate(empty_cap)
        self.assertFalse(result.is_duplicate)
        self.assertEqual(result.failure_count, 0)

    def test_case_sensitivity(self):
        """Test that duplicate detection is case-insensitive."""
        cap1 = "Super Speed"
        cap2 = "super speed"
        cap3 = "SUPER SPEED"
        
        result1 = self.deduplicator.check_duplicate(cap1)
        result2 = self.deduplicator.check_duplicate(cap2)
        result3 = self.deduplicator.check_duplicate(cap3)
        
        self.assertFalse(result1.is_duplicate)
        self.assertTrue(result2.is_duplicate)
        self.assertTrue(result3.is_duplicate)

    def test_whitespace_handling(self):
        """Test that leading/trailing whitespace is handled."""
        cap1 = "  Invisibility  "
        cap2 = "Invisibility"
        
        result1 = self.deduplicator.check_duplicate(cap1)
        result2 = self.deduplicator.check_duplicate(cap2)
        
        self.assertFalse(result1.is_duplicate)
        self.assertTrue(result2.is_duplicate)

    def test_archive_does_not_affect_new_capabilities(self):
        """Test that archived capabilities don't interfere with new ones."""
        # Archive a capability
        cap = "Archived power"
        for i in range(4):
            self.deduplicator.check_duplicate(cap)
        
        # New unique capability should not be affected
        new_cap = "Brand new power"
        result = self.deduplicator.check_duplicate(new_cap)
        self.assertFalse(result.is_duplicate)
        self.assertEqual(result.failure_count, 0)

if __name__ == '__main__':
    unittest.main()