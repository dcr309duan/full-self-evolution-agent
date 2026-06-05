import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.nash_detector import NashEquilibriumDetector
from core.force_generator import ForceGenerator

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

    def test_integration_multi_module_force_generation(self):
        """Integration test: create mock system with 3 modules, register interaction scores,
        verify equilibrium detection, and test multi-module force generation."""
        # (1) Create a mock system with 3 modules
        modules = ["module_x", "module_y", "module_z"]
        
        # (2) Register interaction scores
        interaction_matrix = {
            ("module_x", "module_y"): -0.15,
            ("module_y", "module_x"): -0.15,
            ("module_x", "module_z"): 0.10,
            ("module_z", "module_x"): 0.10,
            ("module_y", "module_z"): -0.05,
            ("module_z", "module_y"): -0.05,
        }

        # Initialize detector with interaction matrix
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)
        
        # Add static scores for all modules
        detector.add_static_score("module_x", 0.80)
        detector.add_static_score("module_y", 0.75)
        detector.add_static_score("module_z", 0.90)

        # (3) Verify equilibrium detection
        equilibrium_state = detector.get_equilibrium_state()
        assert "modules" in equilibrium_state
        assert "scores" in equilibrium_state
        assert "interactions" in equilibrium_state
        assert "is_equilibrium" in equilibrium_state
        assert equilibrium_state["is_equilibrium"] is True
        assert len(equilibrium_state["modules"]) == 3
        assert "module_x" in equilibrium_state["modules"]
        assert "module_y" in equilibrium_state["modules"]
        assert "module_z" in equilibrium_state["modules"]
        assert equilibrium_state["scores"]["module_x"] == 0.80
        assert equilibrium_state["scores"]["module_y"] == 0.75
        assert equilibrium_state["scores"]["module_z"] == 0.90

        # (4) Test multi-module force generation
        force_gen = ForceGenerator(interaction_matrix=interaction_matrix)
        
        # Generate forces for all modules
        forces = force_gen.generate_forces(modules)
        
        # Verify forces are generated for all modules
        assert len(forces) == 3
        for module in modules:
            assert module in forces
            assert isinstance(forces[module], float)
        
        # Verify force directions based on interactions
        # module_x has negative interaction with module_y (-0.15) and positive with module_z (0.10)
        # module_y has negative interaction with module_x (-0.15) and module_z (-0.05)
        # module_z has positive interaction with module_x (0.10) and negative with module_y (-0.05)
        assert forces["module_x"] != 0.0
        assert forces["module_y"] != 0.0
        assert forces["module_z"] != 0.0
        
        # Verify that forces are consistent with equilibrium state
        # In equilibrium, forces should not push modules to change their scores
        assert abs(forces["module_x"]) < 0.5  # Reasonable force magnitude
        assert abs(forces["module_y"]) < 0.5
        assert abs(forces["module_z"]) < 0.5