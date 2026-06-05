import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import ast
import hashlib

# Assuming the module is named 'snapshot_manager' and contains the relevant classes/functions
from snapshot_manager import SnapshotManager, Snapshot

@pytest.fixture
def manager():
    """Fixture to create a SnapshotManager instance."""
    return SnapshotManager()

@pytest.fixture
def sample_ast():
    """Fixture to create a sample AST."""
    return ast.parse("x = 1")

@pytest.fixture
def sample_hash(sample_ast):
    """Fixture to compute hash of sample AST."""
    return hashlib.sha256(ast.dump(sample_ast).encode()).hexdigest()

def test_snapshot_captured_after_mutation_promotion(manager, sample_ast, sample_hash):
    """Test that snapshot is captured after mutation promotion."""
    # Simulate mutation promotion
    manager.promote_mutation(sample_ast)
    
    # Check that a snapshot was created
    assert len(manager.snapshots) == 1
    snapshot = manager.snapshots[0]
    assert snapshot.ast == sample_ast
    assert snapshot.hash == sample_hash
    assert isinstance(snapshot.timestamp, datetime)

def test_get_latest_stable_returns_correct_snapshot(manager, sample_ast, sample_hash):
    """Test that get_latest_stable returns correct snapshot."""
    # Create multiple snapshots
    manager.promote_mutation(sample_ast)
    manager.promote_mutation(ast.parse("y = 2"))
    manager.promote_mutation(ast.parse("z = 3"))
    
    # Mark the second snapshot as stable
    manager.snapshots[1].stable = True
    
    # Get latest stable snapshot
    latest_stable = manager.get_latest_stable()
    
    # Should return the second snapshot (index 1)
    assert latest_stable == manager.snapshots[1]
    assert latest_stable.stable == True
    assert latest_stable.hash == hashlib.sha256(ast.dump(ast.parse("y = 2")).encode()).hexdigest()

def test_multiple_snapshots_stored_and_indexed_correctly(manager, sample_ast):
    """Test that multiple snapshots are stored and indexed correctly."""
    # Create multiple snapshots
    asts = [
        ast.parse("a = 1"),
        ast.parse("b = 2"),
        ast.parse("c = 3"),
        ast.parse("d = 4"),
        ast.parse("e = 5")
    ]
    
    for ast_node in asts:
        manager.promote_mutation(ast_node)
    
    # Check that all snapshots are stored
    assert len(manager.snapshots) == 5
    
    # Check indexing
    for i, snapshot in enumerate(manager.snapshots):
        assert snapshot.index == i
        assert snapshot.ast == asts[i]
        assert snapshot.hash == hashlib.sha256(ast.dump(asts[i]).encode()).hexdigest()

def test_snapshot_pruning_only_last_10_kept(manager, sample_ast):
    """Test that snapshot pruning keeps only the last 10."""
    # Create 15 snapshots
    for i in range(15):
        ast_node = ast.parse(f"var_{i} = {i}")
        manager.promote_mutation(ast_node)
    
    # After pruning, only last 10 should remain
    assert len(manager.snapshots) == 10
    
    # Check that the oldest snapshots were removed
    # The remaining should be indices 5-14 (0-indexed)
    for i, snapshot in enumerate(manager.snapshots):
        expected_index = 5 + i
        assert snapshot.index == expected_index
        assert snapshot.ast == ast.parse(f"var_{expected_index} = {expected_index}")

def test_snapshot_contains_correct_ast_hash_and_timestamp(manager, sample_ast, sample_hash):
    """Test that snapshot contains correct AST, hash, and timestamp."""
    # Capture a snapshot
    manager.promote_mutation(sample_ast)
    
    snapshot = manager.snapshots[0]
    
    # Check AST
    assert ast.dump(snapshot.ast) == ast.dump(sample_ast)
    
    # Check hash
    expected_hash = hashlib.sha256(ast.dump(sample_ast).encode()).hexdigest()
    assert snapshot.hash == expected_hash
    
    # Check timestamp (should be recent)
    assert isinstance(snapshot.timestamp, datetime)
    assert datetime.now() - snapshot.timestamp < timedelta(seconds=5)

def test_snapshot_can_restore_module_to_exact_state(manager, sample_ast):
    """Test that snapshot can be used to restore module to exact state."""
    # Create initial state
    initial_ast = ast.parse("x = 10\ny = 20")
    manager.promote_mutation(initial_ast)
    
    # Modify state
    modified_ast = ast.parse("x = 100\nz = 200")
    manager.promote_mutation(modified_ast)
    
    # Restore to initial snapshot
    restored_ast = manager.restore_snapshot(0)
    
    # Check that restored AST matches initial
    assert ast.dump(restored_ast) == ast.dump(initial_ast)
    
    # Verify the module state is exactly as before
    # (Assuming the manager updates some module state)
    assert manager.current_ast == initial_ast
    assert manager.current_hash == hashlib.sha256(ast.dump(initial_ast).encode()).hexdigest()

def test_snapshot_pruning_after_mutation_promotion(manager, sample_ast):
    """Test that pruning happens automatically after mutation promotion."""
    # Create 12 snapshots (should trigger pruning)
    for i in range(12):
        ast_node = ast.parse(f"var_{i} = {i}")
        manager.promote_mutation(ast_node)
    
    # Should have only 10 snapshots
    assert len(manager.snapshots) == 10
    
    # The oldest two should be gone (indices 0 and 1)
    # Remaining should be indices 2-11
    for i, snapshot in enumerate(manager.snapshots):
        expected_index = 2 + i
        assert snapshot.index == expected_index

def test_get_latest_stable_with_no_stable_snapshots(manager, sample_ast):
    """Test that get_latest_stable returns None when no stable snapshots exist."""
    # Create snapshots but mark none as stable
    manager.promote_mutation(sample_ast)
    manager.promote_mutation(ast.parse("y = 2"))
    
    # All snapshots are unstable
    for snapshot in manager.snapshots:
        snapshot.stable = False
    
    # Should return None
    assert manager.get_latest_stable() is None

def test_get_latest_stable_with_multiple_stable_snapshots(manager, sample_ast):
    """Test that get_latest_stable returns the most recent stable snapshot."""
    # Create multiple snapshots and mark some as stable
    manager.promote_mutation(ast.parse("a = 1"))
    manager.snapshots[0].stable = True
    
    manager.promote_mutation(ast.parse("b = 2"))
    manager.snapshots[1].stable = True
    
    manager.promote_mutation(ast.parse("c = 3"))
    # Third snapshot is not stable
    
    # Should return the second snapshot (most recent stable)
    latest_stable = manager.get_latest_stable()
    assert latest_stable == manager.snapshots[1]
    assert latest_stable.stable == True