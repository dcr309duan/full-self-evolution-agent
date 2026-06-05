import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add the project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mutation_sandbox import MutationSandbox
from test_sandbox import TestSandbox


@pytest.fixture
def sandbox():
    """Create a MutationSandbox instance for testing."""
    sb = MutationSandbox()
    yield sb
    # Ensure cleanup
    sb.cleanup()


@pytest.fixture
def test_sandbox():
    """Create a TestSandbox instance for testing."""
    ts = TestSandbox()
    yield ts
    ts.cleanup()


@pytest.fixture
def temp_project():
    """Create a temporary project directory with a simple Python file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        # Create a simple Python file
        test_file = project_dir / "example.py"
        test_file.write_text("def add(a, b):\n    return a + b\n")
        
        # Create a test file
        test_dir = project_dir / "tests"
        test_dir.mkdir()
        test_file_path = test_dir / "test_example.py"
        test_file_path.write_text(
            "from example import add\n\n"
            "def test_add():\n"
            "    assert add(1, 2) == 3\n\n"
            "def test_add_fail():\n"
            "    assert add(1, 2) == 4\n"
        )
        
        yield project_dir


class TestMutationSandbox:
    """Integration tests for MutationSandbox."""

    @pytest.mark.asyncio
    async def test_start_and_ping(self, sandbox):
        """Test that mutation_sandbox starts and responds to ping."""
        await sandbox.start()
        response = await sandbox.ping()
        assert response == "pong"

    @pytest.mark.asyncio
    async def test_run_trivial_mutation(self, sandbox, temp_project):
        """Test running a trivial mutation (add comment) and verify success."""
        await sandbox.start()
        
        # Create a simple mutation that adds a comment
        mutation = {
            "type": "add_comment",
            "file": str(temp_project / "example.py"),
            "line": 1,
            "comment": "# This is a test comment"
        }
        
        result = await sandbox.run_mutation(mutation)
        assert result["status"] == "success"
        assert "mutated_file" in result
        
        # Verify the comment was added
        mutated_content = Path(result["mutated_file"]).read_text()
        assert "# This is a test comment" in mutated_content

    @pytest.mark.asyncio
    async def test_run_failing_mutation(self, sandbox, temp_project):
        """Test running a failing mutation (syntax error) and verify error response."""
        await sandbox.start()
        
        # Create a mutation that introduces a syntax error
        mutation = {
            "type": "syntax_error",
            "file": str(temp_project / "example.py"),
            "line": 2,
            "new_content": "    return a + b  # missing colon"
        }
        
        result = await sandbox.run_mutation(mutation)
        assert result["status"] == "error"
        assert "error" in result
        assert "SyntaxError" in result.get("error", "") or "syntax" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_timeout_handling(self, sandbox):
        """Test timeout handling."""
        await sandbox.start()
        
        # Create a mutation that would cause a timeout (infinite loop)
        mutation = {
            "type": "infinite_loop",
            "timeout": 0.1  # Very short timeout
        }
        
        with patch.object(sandbox, '_timeout', 0.1):
            result = await sandbox.run_mutation(mutation)
            assert result["status"] == "timeout"
            assert "timeout" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_cleanup_on_shutdown(self, sandbox):
        """Test that sandbox processes are properly cleaned up on shutdown."""
        await sandbox.start()
        
        # Store the process reference
        process = sandbox._process
        
        # Perform cleanup
        await sandbox.cleanup()
        
        # Verify the process is terminated
        if process:
            assert process.returncode is not None
            assert process.poll() is not None


class TestTestSandbox:
    """Integration tests for TestSandbox."""

    @pytest.mark.asyncio
    async def test_run_passing_test(self, test_sandbox, temp_project):
        """Test test_sandbox runs a known passing test."""
        await test_sandbox.start()
        
        result = await test_sandbox.run_test(
            str(temp_project / "tests" / "test_example.py"),
            "test_add"
        )
        
        assert result["status"] == "passed"
        assert result["test_name"] == "test_add"
        assert result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_run_failing_test(self, test_sandbox, temp_project):
        """Test test_sandbox runs a known failing test."""
        await test_sandbox.start()
        
        result = await test_sandbox.run_test(
            str(temp_project / "tests" / "test_example.py"),
            "test_add_fail"
        )
        
        assert result["status"] == "failed"
        assert result["test_name"] == "test_add_fail"
        assert result["exit_code"] != 0
        assert "AssertionError" in result.get("output", "")

    @pytest.mark.asyncio
    async def test_timeout_handling(self, test_sandbox):
        """Test timeout handling in test sandbox."""
        await test_sandbox.start()
        
        # Create a test that would timeout
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_timeout.py"
            test_file.write_text(
                "import time\n"
                "def test_timeout():\n"
                "    time.sleep(10)\n"
                "    assert True\n"
            )
            
            with patch.object(test_sandbox, '_timeout', 0.1):
                result = await test_sandbox.run_test(
                    str(test_file),
                    "test_timeout"
                )
                
                assert result["status"] == "timeout"
                assert "timeout" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_cleanup_on_shutdown(self, test_sandbox):
        """Test that test sandbox processes are properly cleaned up on shutdown."""
        await test_sandbox.start()
        
        # Store the process reference
        process = test_sandbox._process
        
        # Perform cleanup
        await test_sandbox.cleanup()
        
        # Verify the process is terminated
        if process:
            assert process.returncode is not None
            assert process.poll() is not None


@pytest.mark.asyncio
async def test_full_integration():
    """Test full integration between mutation sandbox and test sandbox."""
    mutation_sandbox = MutationSandbox()
    test_sandbox = TestSandbox()
    
    try:
        await mutation_sandbox.start()
        await test_sandbox.start()
        
        # Verify both are running
        assert await mutation_sandbox.ping() == "pong"
        assert await test_sandbox.ping() == "pong"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            
            # Create source file
            source_file = project_dir / "math_utils.py"
            source_file.write_text(
                "def multiply(a, b):\n"
                "    return a * b\n"
            )
            
            # Create test file
            test_dir = project_dir / "tests"
            test_dir.mkdir()
            test_file = test_dir / "test_math_utils.py"
            test_file.write_text(
                "from math_utils import multiply\n\n"
                "def test_multiply():\n"
                "    assert multiply(2, 3) == 6\n"
            )
            
            # Run a mutation
            mutation = {
                "type": "change_operator",
                "file": str(source_file),
                "line": 2,
                "old_operator": "*",
                "new_operator": "+"
            }
            
            mutation_result = await mutation_sandbox.run_mutation(mutation)
            assert mutation_result["status"] == "success"
            
            # Run the test on the mutated file
            test_result = await test_sandbox.run_test(
                str(test_file),
                "test_multiply"
            )
            
            # The test should fail because the mutation changed * to +
            assert test_result["status"] == "failed"
            
    finally:
        mutation_sandbox.cleanup()
        test_sandbox.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])