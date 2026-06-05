import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.nash_detector import NashEquilibriumDetector

class TestNashEquilibriumMinimal:
    """Minimal test for Nash equilibrium detection."""

    def test_initial_no_equilibrium(self):
        """Test that detect_nash() returns False initially."""
        # Create interaction matrix
        interaction_matrix = {
            ("module_a", "module_b"): -0.20,
            ("module_b", "module_a"): -0.20,
        }

        # Initialize detector with interaction matrix
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)

        # Initially, no equilibrium should be detected
        assert detector.detect_nash() is False

    def test_equilibrium_after_static_scores(self):
        """Test that after adding static scores that don't improve, detect_nash() returns True."""
        # Create interaction matrix
        interaction_matrix = {
            ("module_a", "module_b"): -0.20,
            ("module_b", "module_a"): -0.20,
        }

        # Initialize detector with interaction matrix
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)

        # Add static scores that don't improve (simulating equilibrium)
        detector.add_static_score("module_a", 0.85)
        detector.add_static_score("module_b", 0.85)

        # After adding static scores that don't improve, equilibrium should be detected
        assert detector.detect_nash() is True

    def test_equilibrium_state_contains_expected_keys(self):
        """Test that the equilibrium state contains expected keys."""
        # Create interaction matrix
        interaction_matrix = {
            ("module_a", "module_b"): -0.20,
            ("module_b", "module_a"): -0.20,
        }

        # Initialize detector with interaction matrix
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)

        # Add static scores that don't improve
        detector.add_static_score("module_a", 0.85)
        detector.add_static_score("module_b", 0.85)

        # Get equilibrium state
        equilibrium_state = detector.get_equilibrium_state()

        # Verify expected keys are present
        assert "modules" in equilibrium_state
        assert "scores" in equilibrium_state
        assert "interactions" in equilibrium_state
        assert "is_equilibrium" in equilibrium_state

        # Verify the values
        assert equilibrium_state["is_equilibrium"] is True
        assert "module_a" in equilibrium_state["modules"]
        assert "module_b" in equilibrium_state["modules"]
        assert equilibrium_state["scores"]["module_a"] == 0.85
        assert equilibrium_state["scores"]["module_b"] == 0.85