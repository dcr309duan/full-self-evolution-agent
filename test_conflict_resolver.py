import pytest
import json
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil

from conflict_resolver import ConflictResolver, ConflictDetector, ThreeWayMerger
from snapshot_manager import SnapshotManager
from mutation import Mutation

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def snapshot_manager(temp_dir):
    """Create a snapshot manager with temp storage."""
    snap_dir = temp_dir / "snapshots"
    snap_dir.mkdir()
    return SnapshotManager(str(snap_dir))

@pytest.fixture
def conflict_resolver(snapshot_manager):
    """Create a conflict resolver instance."""
    return ConflictResolver(snapshot_manager)

@pytest.fixture
def sample_mutations():
    """Create sample mutations for testing."""
    mut1 = Mutation(
        mutation_id="mut_001",
        function_name="calculate_total",
        start_line=10,
        end_line=15,
        original_code="def calculate_total(items):\n    total = 0\n    for item in items:\n        total += item\n    return total\n",
        mutated_code="def calculate_total(items):\n    total = 0\n    for item in items:\n        total += item * 2\n    return total\n",
        timestamp=datetime.now()
    )
    mut2 = Mutation(
        mutation_id="mut_002",
        function_name="calculate_total",
        start_line=10,
        end_line=15,
        original_code="def calculate_total(items):\n    total = 0\n    for item in items:\n        total += item\n    return total\n",
        mutated_code="def calculate_total(items):\n    total = 1\n    for item in items:\n        total += item\n    return total\n",
        timestamp=datetime.now()
    )
    mut3 = Mutation(
        mutation_id="mut_003",
        function_name="process_data",
        start_line=20,
        end_line=25,
        original_code="def process_data(data):\n    result = []\n    for d in data:\n        result.append(d * 2)\n    return result\n",
        mutated_code="def process_data(data):\n    result = []\n    for d in data:\n        result.append(d * 3)\n    return result\n",
        timestamp=datetime.now()
    )
    return mut1, mut2, mut3

class TestConflictDetector:
    """Tests for conflict detection functionality."""

    def test_overlapping_mutations_detected(self, sample_mutations):
        """Test that overlapping mutations (same function, same line range) are detected."""
        mut1, mut2, _ = sample_mutations
        detector = ConflictDetector()
        
        conflicts = detector.detect_conflicts([mut1, mut2])
        
        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict['type'] == 'overlapping'
        assert conflict['mutations'] == ['mut_001', 'mut_002']
        assert conflict['function'] == 'calculate_total'
        assert conflict['line_range'] == (10, 15)

    def test_non_overlapping_mutations_not_flagged(self, sample_mutations):
        """Test that non-overlapping mutations are not flagged as conflicts."""
        mut1, _, mut3 = sample_mutations
        detector = ConflictDetector()
        
        conflicts = detector.detect_conflicts([mut1, mut3])
        
        assert len(conflicts) == 0

    def test_partial_overlap_detected(self):
        """Test that partially overlapping mutations are detected."""
        mut1 = Mutation(
            mutation_id="mut_001",
            function_name="calculate",
            start_line=10,
            end_line=20,
            original_code="",
            mutated_code="",
            timestamp=datetime.now()
        )
        mut2 = Mutation(
            mutation_id="mut_002",
            function_name="calculate",
            start_line=15,
            end_line=25,
            original_code="",
            mutated_code="",
            timestamp=datetime.now()
        )
        detector = ConflictDetector()
        
        conflicts = detector.detect_conflicts([mut1, mut2])
        
        assert len(conflicts) == 1
        assert conflicts[0]['mutations'] == ['mut_001', 'mut_002']

    def test_no_conflicts_with_different_functions(self, sample_mutations):
        """Test that mutations in different functions don't conflict."""
        mut1, _, mut3 = sample_mutations
        detector = ConflictDetector()
        
        conflicts = detector.detect_conflicts([mut1, mut3])
        
        assert len(conflicts) == 0

class TestThreeWayMerger:
    """Tests for three-way merge functionality."""

    def test_merge_succeeds_non_conflicting_changes(self, temp_dir):
        """Test that three-way merge succeeds with non-conflicting changes to same region."""
        base_code = "x = 10\ny = 20\nz = 30\n"
        change1 = "x = 15\ny = 20\nz = 30\n"  # Changed x
        change2 = "x = 10\ny = 25\nz = 30\n"  # Changed y
        
        merger = ThreeWayMerger()
        result = merger.merge(base_code, change1, change2)
        
        assert result['success'] == True
        assert result['merged_code'] == "x = 15\ny = 25\nz = 30\n"

    def test_merge_fails_conflicting_changes(self, temp_dir):
        """Test that three-way merge fails with truly conflicting changes."""
        base_code = "x = 10\ny = 20\n"
        change1 = "x = 15\ny = 20\n"  # Changed x to 15
        change2 = "x = 25\ny = 20\n"  # Changed x to 25 (conflict)
        
        merger = ThreeWayMerger()
        result = merger.merge(base_code, change1, change2)
        
        assert result['success'] == False
        assert 'conflict' in result['error'].lower()

    def test_merge_with_identical_changes(self):
        """Test that identical changes don't cause conflicts."""
        base_code = "value = 100\n"
        change1 = "value = 200\n"
        change2 = "value = 200\n"
        
        merger = ThreeWayMerger()
        result = merger.merge(base_code, change1, change2)
        
        assert result['success'] == True
        assert result['merged_code'] == "value = 200\n"

    def test_merge_with_no_changes(self):
        """Test merging when no changes are made."""
        base_code = "unchanged = True\n"
        change1 = "unchanged = True\n"
        change2 = "unchanged = True\n"
        
        merger = ThreeWayMerger()
        result = merger.merge(base_code, change1, change2)
        
        assert result['success'] == True
        assert result['merged_code'] == base_code

class TestConflictResolver:
    """Tests for the main ConflictResolver class."""

    def test_detect_and_resolve_overlapping(self, conflict_resolver, sample_mutations, temp_dir):
        """Test that overlapping mutations are detected and flagged."""
        mut1, mut2, _ = sample_mutations
        
        result = conflict_resolver.resolve([mut1, mut2])
        
        assert result['has_conflicts'] == True
        assert len(result['conflicts']) == 1
        assert result['resolved'] == False

    def test_detect_and_resolve_non_overlapping(self, conflict_resolver, sample_mutations, temp_dir):
        """Test that non-overlapping mutations pass through."""
        mut1, _, mut3 = sample_mutations
        
        result = conflict_resolver.resolve([mut1, mut3])
        
        assert result['has_conflicts'] == False
        assert result['resolved'] == True

    def test_three_way_merge_success(self, conflict_resolver, snapshot_manager, temp_dir):
        """Test three-way merge succeeds with non-conflicting changes."""
        # Create base snapshot
        base_code = "def add(a, b):\n    return a + b\n"
        snapshot_id = snapshot_manager.create_snapshot("test_file.py", base_code)
        
        # Create mutations with non-conflicting changes
        mut1 = Mutation(
            mutation_id="mut_001",
            function_name="add",
            start_line=1,
            end_line=2,
            original_code=base_code,
            mutated_code="def add(a, b):\n    return a + b + 1\n",
            timestamp=datetime.now()
        )
        mut2 = Mutation(
            mutation_id="mut_002",
            function_name="add",
            start_line=1,
            end_line=2,
            original_code=base_code,
            mutated_code="def add(a, b):\n    return a + b * 2\n",
            timestamp=datetime.now()
        )
        
        result = conflict_resolver.resolve_with_base(
            snapshot_id, 
            "test_file.py", 
            [mut1, mut2]
        )
        
        assert result['success'] == True
        assert result['merged'] == True

    def test_three_way_merge_failure_reverts(self, conflict_resolver, snapshot_manager, temp_dir):
        """Test three-way merge fails with conflicting changes and both mutations reverted."""
        base_code = "result = 100\n"
        snapshot_id = snapshot_manager.create_snapshot("test_file.py", base_code)
        
        # Create mutations with conflicting changes to same line
        mut1 = Mutation(
            mutation_id="mut_001",
            function_name="test_func",
            start_line=1,
            end_line=1,
            original_code=base_code,
            mutated_code="result = 200\n",
            timestamp=datetime.now()
        )
        mut2 = Mutation(
            mutation_id="mut_002",
            function_name="test_func",
            start_line=1,
            end_line=1,
            original_code=base_code,
            mutated_code="result = 300\n",
            timestamp=datetime.now()
        )
        
        result = conflict_resolver.resolve_with_base(
            snapshot_id,
            "test_file.py",
            [mut1, mut2]
        )
        
        assert result['success'] == False
        assert result['reverted'] == True
        assert result['revert_reason'] == 'conflict'

    def test_conflict_log_written(self, conflict_resolver, sample_mutations, temp_dir):
        """Test that conflict_log is properly written with mutation IDs, timestamps, and diff details."""
        mut1, mut2, _ = sample_mutations
        
        # Ensure log directory exists
        log_dir = temp_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        conflict_resolver.log_dir = str(log_dir)
        
        result = conflict_resolver.resolve([mut1, mut2])
        
        # Check that log file was created
        log_files = list(log_dir.glob("conflict_*.log"))
        assert len(log_files) > 0
        
        # Read the latest log file
        latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
        log_content = latest_log.read_text()
        
        # Verify log content
        assert "mut_001" in log_content
        assert "mut_002" in log_content
        assert "calculate_total" in log_content
        assert "10-15" in log_content
        assert "overlapping" in log_content

    def test_integration_with_snapshot_manager(self, conflict_resolver, snapshot_manager, temp_dir):
        """Test integration with snapshot_manager for base snapshot retrieval."""
        # Create a snapshot
        original_code = "def multiply(a, b):\n    return a * b\n"
        snapshot_id = snapshot_manager.create_snapshot("math.py", original_code)
        
        # Verify snapshot exists
        snapshot = snapshot_manager.get_snapshot(snapshot_id)
        assert snapshot is not None
        assert snapshot['code'] == original_code
        
        # Test conflict resolver can retrieve base snapshot
        base_code = conflict_resolver.get_base_code(snapshot_id, "math.py")
        assert base_code == original_code

    def test_revert_to_snapshot_restores_original_state(self, conflict_resolver, snapshot_manager, temp_dir):
        """Test that reverting to snapshot restores exact original state."""
        original_code = "def divide(a, b):\n    return a / b\n"
        snapshot_id = snapshot_manager.create_snapshot("calc.py", original_code)
        
        # Simulate changes
        modified_code = "def divide(a, b):\n    return a // b\n"
        
        # Revert to snapshot
        conflict_resolver.revert_to_snapshot(snapshot_id, "calc.py")
        
        # Verify restoration
        restored_code = snapshot_manager.get_snapshot(snapshot_id)['code']
        assert restored_code == original_code
        assert restored_code != modified_code

    def test_multiple_conflicts_logged_separately(self, conflict_resolver, temp_dir):
        """Test that multiple conflicts are logged as separate entries."""
        log_dir = temp_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        conflict_resolver.log_dir = str(log_dir)
        
        # Create multiple conflicting mutation pairs
        mut1 = Mutation(
            mutation_id="mut_001",
            function_name="func_a",
            start_line=1,
            end_line=3,
            original_code="",
            mutated_code="",
            timestamp=datetime.now()
        )
        mut2 = Mutation(
            mutation_id="mut_002",
            function_name="func_a",
            start_line=1,
            end_line=3,
            original_code="",
            mutated_code="",
            timestamp=datetime.now()
        )
        mut3 = Mutation(
            mutation_id="mut_003",
            function_name="func_b",
            start_line=5,
            end_line=7,
            original_code="",
            mutated_code="",
            timestamp=datetime.now()
        )
        mut4 = Mutation(
            mutation_id="mut_004",
            function_name="func_b",
            start_line=5,
            end_line=7,
            original_code="",
            mutated_code="",
            timestamp=datetime.now()
        )
        
        result = conflict_resolver.resolve([mut1, mut2, mut3, mut4])
        
        assert result['has_conflicts'] == True
        assert len(result['conflicts']) == 2
        
        # Verify two log entries
        log_files = list(log_dir.glob("conflict_*.log"))
        assert len(log_files) >= 2

    def test_conflict_resolution_with_timestamps(self, conflict_resolver, temp_dir):
        """Test that conflict resolution properly handles timestamps."""
        log_dir = temp_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        conflict_resolver.log_dir = str(log_dir)
        
        old_mutation = Mutation(
            mutation_id="mut_old",
            function_name="test",
            start_line=1,
            end_line=5,
            original_code="",
            mutated_code="",
            timestamp=datetime(2023, 1, 1)
        )
        new_mutation = Mutation(
            mutation_id="mut_new",
            function_name="test",
            start_line=1,
            end_line=5,
            original_code="",
            mutated_code="",
            timestamp=datetime(2023, 6, 1)
        )
        
        result = conflict_resolver.resolve([old_mutation, new_mutation])
        
        assert result['has_conflicts'] == True
        # Verify timestamps are in log
        log_files = list(log_dir.glob("conflict_*.log"))
        latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
        log_content = latest_log.read_text()
        assert "2023-01-01" in log_content or "2023-06-01" in log_content

if __name__ == "__main__":
    pytest.main([__file__])