import os
import sys
import tempfile
import shutil
import time
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.nash_detector import NashDetector
from core.multi_module_forcer import MultiModuleForcer


class TestNashBreaking(unittest.TestCase):
    """Test Nash equilibrium detection and forcing with dummy modules."""

    def setUp(self):
        """Create temporary directory with 3 dummy module files."""
        self.test_dir = tempfile.mkdtemp()
        self.module_paths = []
        
        # Create 3 dummy module files
        for i in range(3):
            module_path = os.path.join(self.test_dir, f"dummy_module_{i}.py")
            with open(module_path, 'w') as f:
                f.write(f"# Dummy module {i}\n")
                f.write(f"VERSION = {i}\n")
                f.write(f"def get_value():\n")
                f.write(f"    return {i * 10}\n")
            self.module_paths.append(module_path)
        
        # Initialize detector and forcer
        self.detector = NashDetector()
        self.forcer = MultiModuleForcer(self.module_paths)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_equilibrium_detection(self):
        """Test that detector identifies equilibrium after no changes for 3 cycles."""
        # Initially not in equilibrium
        self.assertFalse(self.detector.is_in_equilibrium(self.module_paths))
        
        # Simulate 3 cycles with no changes
        for _ in range(3):
            self.detector.record_state(self.module_paths)
            time.sleep(0.01)  # Small delay to ensure timestamps differ
        
        # Now should be in equilibrium
        self.assertTrue(self.detector.is_in_equilibrium(self.module_paths))
        
        # Verify equilibrium count
        self.assertEqual(self.detector.get_equilibrium_count(), 3)

    def test_forcer_generates_changes(self):
        """Test that forcer generates coordinated changes across modules."""
        # Get initial states
        initial_contents = {}
        for path in self.module_paths:
            with open(path, 'r') as f:
                initial_contents[path] = f.read()
        
        # Force changes
        changes = self.forcer.force_coordinated_changes()
        
        # Verify changes were made
        self.assertTrue(len(changes) > 0)
        
        # Verify each module was modified
        for path in self.module_paths:
            with open(path, 'r') as f:
                new_content = f.read()
            self.assertNotEqual(initial_contents[path], new_content,
                              f"Module {path} was not modified")

    def test_full_cycle(self):
        """Test complete cycle: detect equilibrium, force changes, verify new state."""
        # Step 1: Wait for equilibrium
        for _ in range(3):
            self.detector.record_state(self.module_paths)
            time.sleep(0.01)
        
        # Step 2: Verify equilibrium detected
        self.assertTrue(self.detector.is_in_equilibrium(self.module_paths))
        
        # Step 3: Force changes
        changes = self.forcer.force_coordinated_changes()
        self.assertTrue(len(changes) > 0)
        
        # Step 4: Verify equilibrium is broken
        self.assertFalse(self.detector.is_in_equilibrium(self.module_paths))
        
        # Step 5: Verify modules were modified
        for path in self.module_paths:
            with open(path, 'r') as f:
                content = f.read()
            self.assertIn("VERSION", content)

    def test_multiple_force_cycles(self):
        """Test multiple force cycles maintain module integrity."""
        for cycle in range(3):
            # Record state
            self.detector.record_state(self.module_paths)
            
            # Force changes
            changes = self.forcer.force_coordinated_changes()
            
            # Verify changes were made
            self.assertTrue(len(changes) > 0,
                          f"No changes in cycle {cycle}")
            
            # Verify modules still valid Python
            for path in self.module_paths:
                try:
                    compile(open(path).read(), path, 'exec')
                except SyntaxError as e:
                    self.fail(f"Module {path} has invalid syntax after cycle {cycle}: {e}")


if __name__ == '__main__':
    unittest.main()