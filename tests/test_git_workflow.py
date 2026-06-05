import pytest
import os
import tempfile
import shutil
import subprocess
from pathlib import Path


@pytest.fixture
def git_repo():
    """Create a temporary directory with a git repository and test modules."""
    tmp_dir = tempfile.mkdtemp()
    original_cwd = os.getcwd()
    os.chdir(tmp_dir)
    
    # Initialize git repo
    subprocess.run(["git", "init"], capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], capture_output=True)
    
    # Create test modules
    (Path(tmp_dir) / "module_a.py").write_text("def foo():\n    return 1\n")
    (Path(tmp_dir) / "module_b.py").write_text("def bar():\n    return 2\n")
    
    # Initial commit
    subprocess.run(["git", "add", "."], capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], capture_output=True)
    
    yield tmp_dir
    
    os.chdir(original_cwd)
    shutil.rmtree(tmp_dir)


def simulate_mutation(repo_path, commit_message):
    """Simulate a successful mutation by modifying a file and committing."""
    os.chdir(repo_path)
    module_a = Path(repo_path) / "module_a.py"
    module_a.write_text("def foo():\n    return 100\n")
    subprocess.run(["git", "add", "."], capture_output=True)
    result = subprocess.run(["git", "commit", "-m", commit_message], capture_output=True, text=True)
    return result.returncode == 0


def simulate_failed_mutation(repo_path):
    """Simulate a failed mutation by modifying a file and then reverting."""
    os.chdir(repo_path)
    module_b = Path(repo_path) / "module_b.py"
    original_content = module_b.read_text()
    module_b.write_text("def bar():\n    return 200\n")
    # Simulate failure by reverting the change
    subprocess.run(["git", "checkout", "--", "module_b.py"], capture_output=True)
    return module_b.read_text() == original_content


def test_successful_mutation_commit(git_repo):
    """Test that a successful mutation creates a 'mutation: success' commit."""
    assert simulate_mutation(git_repo, "mutation: success")
    
    # Verify the commit exists
    result = subprocess.run(["git", "log", "--oneline", "--grep=mutation: success"], 
                          capture_output=True, text=True)
    assert "mutation: success" in result.stdout


def test_failed_mutation_reverts_working_tree(git_repo):
    """Test that a failed mutation reverts the working tree to pre-mutation state."""
    # Get the current state
    initial_status = subprocess.run(["git", "status", "--porcelain"], 
                                   capture_output=True, text=True).stdout
    
    assert simulate_failed_mutation(git_repo)
    
    # Verify working tree is clean and unchanged
    final_status = subprocess.run(["git", "status", "--porcelain"], 
                                 capture_output=True, text=True).stdout
    assert initial_status == final_status


def test_multiple_rollbacks_in_sequence(git_repo):
    """Test that multiple rollbacks in sequence work correctly."""
    # Create several mutations and rollbacks
    for i in range(3):
        # Make a change
        module_a = Path(git_repo) / "module_a.py"
        module_a.write_text(f"def foo():\n    return {i + 1}\n")
        
        # Rollback
        subprocess.run(["git", "checkout", "--", "module_a.py"], capture_output=True)
        
        # Verify original content
        assert module_a.read_text() == "def foo():\n    return 1\n"
    
    # Verify git log still has only initial commit
    result = subprocess.run(["git", "log", "--oneline"], capture_output=True, text=True)
    assert len(result.stdout.strip().split('\n')) == 1


def test_git_stash_handles_dirty_working_tree(git_repo):
    """Test that git stash mechanism handles dirty working trees."""
    # Create a dirty working tree
    module_a = Path(git_repo) / "module_a.py"
    module_a.write_text("def foo():\n    return 999\n")
    
    # Verify dirty state
    status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    assert "M module_a.py" in status.stdout
    
    # Stash the changes
    stash_result = subprocess.run(["git", "stash"], capture_output=True, text=True)
    assert stash_result.returncode == 0
    
    # Verify working tree is clean
    clean_status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    assert clean_status.stdout == ""
    
    # Apply stash back
    pop_result = subprocess.run(["git", "stash", "pop"], capture_output=True, text=True)
    assert pop_result.returncode == 0
    
    # Verify changes are back
    assert module_a.read_text() == "def foo():\n    return 999\n"