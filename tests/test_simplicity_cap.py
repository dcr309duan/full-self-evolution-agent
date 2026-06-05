import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import logging

# Assuming the main module is named 'simplicity_cap' and contains the relevant functions
from simplicity_cap import (
    check_mutation_size,
    apply_mutation,
    rollback_mutation,
    get_complexity_debt,
    set_consolidation_required,
    CONSOLIDATION_THRESHOLD,
    MAX_MUTATION_PERCENT,
    LOG_FILE
)

@pytest.fixture
def temp_project():
    """Create a temporary project directory with a sample Python file."""
    tmp_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    os.chdir(tmp_dir)
    
    # Create a sample Python file with known LOC
    sample_file = Path(tmp_dir) / "sample.py"
    sample_file.write_text("""def foo():
    pass

def bar():
    return 42

x = 1
y = 2
z = 3
""")
    
    yield tmp_dir
    
    os.chdir(original_dir)
    shutil.rmtree(tmp_dir)

@pytest.fixture
def setup_logging():
    """Set up logging to capture complexity debt logs."""
    logger = logging.getLogger('simplicity_cap')
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    yield handler
    logger.removeHandler(handler)

def test_small_mutation_accepted(temp_project):
    """Test that a small mutation (1% LOC increase) is accepted."""
    project_dir = temp_project
    file_path = Path(project_dir) / "sample.py"
    
    # Get original LOC
    original_loc = len(file_path.read_text().splitlines())
    
    # Simulate a small mutation (add 1% more lines)
    lines_to_add = max(1, int(original_loc * 0.01))
    mutation_content = "\n".join([f"# new line {i}" for i in range(lines_to_add)])
    
    # Apply mutation
    result = apply_mutation(file_path, mutation_content)
    
    # Verify mutation was accepted
    assert result is True, "Small mutation should be accepted"
    
    # Verify file was modified
    new_loc = len(file_path.read_text().splitlines())
    assert new_loc == original_loc + lines_to_add, f"Expected {original_loc + lines_to_add} lines, got {new_loc}"

def test_large_mutation_reverted(temp_project):
    """Test that a large mutation (10% LOC increase) is reverted."""
    project_dir = temp_project
    file_path = Path(project_dir) / "sample.py"
    
    # Get original content and LOC
    original_content = file_path.read_text()
    original_loc = len(original_content.splitlines())
    
    # Simulate a large mutation (add 10% more lines)
    lines_to_add = max(1, int(original_loc * 0.10))
    mutation_content = "\n".join([f"# new line {i}" for i in range(lines_to_add)])
    
    # Apply mutation (should be reverted)
    result = apply_mutation(file_path, mutation_content)
    
    # Verify mutation was reverted
    assert result is False, "Large mutation should be reverted"
    
    # Verify file content is unchanged (rollback preserved original)
    current_content = file_path.read_text()
    assert current_content == original_content, "File content should be unchanged after rollback"

def test_consolidation_required_trigger(temp_project):
    """Test that consolidation_required flag triggers at 3% threshold."""
    project_dir = temp_project
    file_path = Path(project_dir) / "sample.py"
    
    # Get original LOC
    original_loc = len(file_path.read_text().splitlines())
    
    # Simulate a mutation that increases LOC by 3% (the threshold)
    lines_to_add = max(1, int(original_loc * 0.03))
    mutation_content = "\n".join([f"# new line {i}" for i in range(lines_to_add)])
    
    # Apply mutation
    apply_mutation(file_path, mutation_content)
    
    # Check if consolidation_required flag is set
    # This assumes there's a function to check the flag or it's stored somewhere
    consolidation_flag = get_complexity_debt()  # Hypothetical function
    assert consolidation_flag is True, "Consolidation flag should be triggered at 3% threshold"
    
    # Alternatively, check if the flag is set in a global state
    # Assuming there's a module-level variable or function
    from simplicity_cap import is_consolidation_required
    assert is_consolidation_required() is True, "Consolidation should be required"

def test_complexity_debt_logged(temp_project, setup_logging):
    """Test that complexity debt is properly logged."""
    project_dir = temp_project
    file_path = Path(project_dir) / "sample.py"
    
    # Get original LOC
    original_loc = len(file_path.read_text().splitlines())
    
    # Simulate a mutation that increases LOC by 5% (above threshold)
    lines_to_add = max(1, int(original_loc * 0.05))
    mutation_content = "\n".join([f"# new line {i}" for i in range(lines_to_add)])
    
    # Capture log output
    with patch('logging.Logger.info') as mock_log:
        apply_mutation(file_path, mutation_content)
        
        # Verify that complexity debt was logged
        # The log message should contain information about the debt
        log_calls = mock_log.call_args_list
        debt_logged = any('complexity debt' in str(call).lower() for call in log_calls)
        assert debt_logged, "Complexity debt should be logged"
        
        # Alternatively, check for specific log message
        # Assuming log format: "Complexity debt increased by X% (total: Y%)"
        expected_message = f"Complexity debt increased by {lines_to_add/original_loc*100:.1f}%"
        assert any(expected_message in str(call) for call in log_calls), f"Expected log message: {expected_message}"

def test_rollback_preserves_original_state(temp_project):
    """Test that rollback preserves original file state."""
    project_dir = temp_project
    file_path = Path(project_dir) / "sample.py"
    
    # Get original content
    original_content = file_path.read_text()
    
    # Simulate a mutation that will be reverted
    mutation_content = "# This mutation should be rolled back\n" * 10
    
    # Apply mutation (should trigger rollback if too large)
    apply_mutation(file_path, mutation_content)
    
    # Verify file content is exactly the same as original
    current_content = file_path.read_text()
    assert current_content == original_content, "File content should be preserved after rollback"
    
    # Also verify file metadata (permissions, etc.) if applicable
    # For simplicity, just check content

def test_rollback_with_backup(temp_project):
    """Test that rollback uses backup file to restore original state."""
    project_dir = temp_project
    file_path = Path(project_dir) / "sample.py"
    backup_path = file_path.with_suffix('.bak')
    
    # Get original content
    original_content = file_path.read_text()
    
    # Create a backup file (simulating what the module might do)
    backup_path.write_text(original_content)
    
    # Simulate a mutation that will be reverted
    mutation_content = "# This mutation should be rolled back\n" * 10
    
    # Apply mutation (should trigger rollback)
    apply_mutation(file_path, mutation_content)
    
    # Verify that backup file exists and matches original
    assert backup_path.exists(), "Backup file should exist"
    backup_content = backup_path.read_text()
    assert backup_content == original_content, "Backup file should contain original content"
    
    # Verify current file matches original (restored from backup)
    current_content = file_path.read_text()
    assert current_content == original_content, "File should be restored from backup"

if __name__ == "__main__":
    pytest.main([__file__])