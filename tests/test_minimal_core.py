"""Test for minimal_core_bootstrap module."""

import sys
import os
import pytest

# Add parent directory to path to import minimal_core_bootstrap
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import minimal_core_bootstrap


class TestMinimalCoreBootstrap:
    """Test suite for minimal_core_bootstrap module."""

    def test_evolution_loop_runs_without_exceptions(self):
        """Test that the evolution loop runs for 3 cycles without raising exceptions."""
        try:
            minimal_core_bootstrap.main()
        except Exception as e:
            pytest.fail(f"Evolution loop raised an exception: {e}")

    def test_state_transitions_are_valid(self):
        """Test that state transitions follow the expected pattern."""
        # Capture the output
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            minimal_core_bootstrap.main()
        
        output = f.getvalue()
        lines = output.strip().split('\n')
        
        # Check that we have at least 3 cycles
        assert len(lines) >= 3, f"Expected at least 3 cycles, got {len(lines)}"
        
        # Check that each line follows the expected pattern: "Cycle N: State -> NextState"
        for i, line in enumerate(lines[:3], 1):
            assert line.startswith(f"Cycle {i}:"), f"Line {i} doesn't start with 'Cycle {i}:': {line}"
            assert "->" in line, f"Line {i} doesn't contain '->': {line}"
            
            # Extract state and next state
            parts = line.split(":")[1].strip().split("->")
            assert len(parts) == 2, f"Line {i} doesn't have exactly 2 parts separated by '->': {line}"
            
            current_state = parts[0].strip()
            next_state = parts[1].strip()
            
            # Verify states are non-empty strings
            assert current_state, f"Current state is empty in line {i}"
            assert next_state, f"Next state is empty in line {i}"

    def test_output_matches_expected_pattern(self):
        """Test that the output matches the expected pattern for 3 cycles."""
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            minimal_core_bootstrap.main()
        
        output = f.getvalue()
        lines = output.strip().split('\n')
        
        # Verify exactly 3 cycles
        assert len(lines) == 3, f"Expected exactly 3 cycles, got {len(lines)}"
        
        # Verify each line matches expected pattern
        expected_patterns = [
            r"^Cycle 1: \w+ -> \w+$",
            r"^Cycle 2: \w+ -> \w+$",
            r"^Cycle 3: \w+ -> \w+$",
        ]
        
        for i, (line, pattern) in enumerate(zip(lines, expected_patterns), 1):
            import re
            assert re.match(pattern, line), f"Line {i} '{line}' doesn't match pattern '{pattern}'"

    def test_state_consistency(self):
        """Test that the next state of one cycle matches the current state of the next cycle."""
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            minimal_core_bootstrap.main()
        
        output = f.getvalue()
        lines = output.strip().split('\n')
        
        # Extract states from each line
        states = []
        for line in lines:
            parts = line.split(":")[1].strip().split("->")
            current_state = parts[0].strip()
            next_state = parts[1].strip()
            states.append((current_state, next_state))
        
        # Check that next state of cycle N matches current state of cycle N+1
        for i in range(len(states) - 1):
            assert states[i][1] == states[i+1][0], \
                f"State mismatch: Cycle {i+1} next state '{states[i][1]}' != Cycle {i+2} current state '{states[i+1][0]}'"