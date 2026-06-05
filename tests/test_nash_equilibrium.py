import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.nash_detector import NashEquilibriumDetector
from core.multi_module_forcer import MultiModuleForcer

class TestNashEquilibriumMinimal:
    """Minimal integration test for Nash equilibrium detection and multi-module forcing."""

    def test_equilibrium_with_stable_scores(self):
        """Test that nash_detector correctly identifies equilibrium state when module scores are stable."""
        # Create interaction matrix with stable interactions
        interaction_matrix = {
            ("module_a", "module_b"): -0.20,
            ("module_b", "module_a"): -0.20,
        }

        # Initialize detector with interaction matrix
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)

        # Add static scores that don't improve (simulating equilibrium)
        detector.add_static_score("module_a", 0.85)
        detector.add_static_score("module_b", 0.85)

        # Verify equilibrium detection
        assert detector.detect_nash() is True

        # Get equilibrium state and verify structure
        equilibrium_state = detector.get_equilibrium_state()
        assert "modules" in equilibrium_state
        assert "scores" in equilibrium_state
        assert "interactions" in equilibrium_state
        assert "is_equilibrium" in equilibrium_state
        assert equilibrium_state["is_equilibrium"] is True
        assert "module_a" in equilibrium_state["modules"]
        assert "module_b" in equilibrium_state["modules"]
        assert equilibrium_state["scores"]["module_a"] == 0.85
        assert equilibrium_state["scores"]["module_b"] == 0.85

    def test_multi_module_plan_generation(self):
        """Test that multi_module_forcer generates a valid multi-module plan."""
        # Create interaction matrix
        interaction_matrix = {
            ("module_x", "module_y"): -0.15,
            ("module_y", "module_x"): -0.15,
            ("module_x", "module_z"): 0.10,
            ("module_z", "module_x"): 0.10,
            ("module_y", "module_z"): -0.05,
            ("module_z", "module_y"): -0.05,
        }

        # Initialize forcer with interaction matrix
        forcer = MultiModuleForcer(interaction_matrix=interaction_matrix)

        # Define modules to include in the plan
        modules = ["module_x", "module_y", "module_z"]

        # Generate multi-module plan
        plan = forcer.generate_multi_module_plan(modules)

        # Verify plan structure
        assert "modules" in plan
        assert "forces" in plan
        assert "interactions" in plan
        assert len(plan["modules"]) == 3
        assert "module_x" in plan["modules"]
        assert "module_y" in plan["modules"]
        assert "module_z" in plan["modules"]

        # Verify forces are generated for all modules
        forces = plan["forces"]
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

        # Verify that forces are within reasonable magnitude
        assert abs(forces["module_x"]) < 1.0
        assert abs(forces["module_y"]) < 1.0
        assert abs(forces["module_z"]) < 1.0

        # Verify interactions are included in the plan
        assert len(plan["interactions"]) == 6
        for key in interaction_matrix:
            assert key in plan["interactions"]
            assert plan["interactions"][key] == interaction_matrix[key]

    def test_integration_equilibrium_and_plan(self):
        """Integration test: verify equilibrium detection and plan generation work together."""
        # Create interaction matrix
        interaction_matrix = {
            ("module_a", "module_b"): -0.20,
            ("module_b", "module_a"): -0.20,
        }

        # Initialize detector and forcer
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)
        forcer = MultiModuleForcer(interaction_matrix=interaction_matrix)

        # Add stable scores to detector
        detector.add_static_score("module_a", 0.85)
        detector.add_static_score("module_b", 0.85)

        # Verify equilibrium
        assert detector.detect_nash() is True

        # Generate plan for the same modules
        modules = ["module_a", "module_b"]
        plan = forcer.generate_multi_module_plan(modules)

        # Verify plan is valid
        assert "modules" in plan
        assert "forces" in plan
        assert len(plan["modules"]) == 2
        assert "module_a" in plan["modules"]
        assert "module_b" in plan["modules"]

        # Verify forces are generated
        forces = plan["forces"]
        assert len(forces) == 2
        assert "module_a" in forces
        assert "module_b" in forces
        assert isinstance(forces["module_a"], float)
        assert isinstance(forces["module_b"], float)

        # In equilibrium, forces should be consistent with stable scores
        assert abs(forces["module_a"]) < 0.5
        assert abs(forces["module_b"]) < 0.5

        # Verify equilibrium state matches plan
        equilibrium_state = detector.get_equilibrium_state()
        assert equilibrium_state["is_equilibrium"] is True
        assert equilibrium_state["scores"]["module_a"] == 0.85
        assert equilibrium_state["scores"]["module_b"] == 0.85

    def test_three_module_local_optimum(self):
        """Test that nash_detector correctly identifies equilibrium in a 3-module local optimum
        and multi_module_forcer generates a coordinated change."""
        # Create interaction matrix for 3 modules with local optimum configuration
        # Module A and B have strong negative interaction (local optimum trap)
        # Module C has weak positive interaction with both A and B
        interaction_matrix = {
            ("module_a", "module_b"): -0.30,
            ("module_b", "module_a"): -0.30,
            ("module_a", "module_c"): 0.05,
            ("module_c", "module_a"): 0.05,
            ("module_b", "module_c"): 0.05,
            ("module_c", "module_b"): 0.05,
        }

        # Initialize detector and forcer
        detector = NashEquilibriumDetector(interaction_matrix=interaction_matrix)
        forcer = MultiModuleForcer(interaction_matrix=interaction_matrix)

        # Add scores that represent a local optimum:
        # - Module A and B have high scores but are stuck due to negative interaction
        # - Module C has lower score but positive interactions
        detector.add_static_score("module_a", 0.90)
        detector.add_static_score("module_b", 0.90)
        detector.add_static_score("module_c", 0.70)

        # Verify equilibrium detection
        assert detector.detect_nash() is True

        # Get equilibrium state and verify structure
        equilibrium_state = detector.get_equilibrium_state()
        assert equilibrium_state["is_equilibrium"] is True
        assert len(equilibrium_state["modules"]) == 3
        assert "module_a" in equilibrium_state["modules"]
        assert "module_b" in equilibrium_state["modules"]
        assert "module_c" in equilibrium_state["modules"]
        assert equilibrium_state["scores"]["module_a"] == 0.90
        assert equilibrium_state["scores"]["module_b"] == 0.90
        assert equilibrium_state["scores"]["module_c"] == 0.70

        # Generate multi-module plan for all three modules
        modules = ["module_a", "module_b", "module_c"]
        plan = forcer.generate_multi_module_plan(modules)

        # Verify plan structure
        assert "modules" in plan
        assert "forces" in plan
        assert "interactions" in plan
        assert len(plan["modules"]) == 3

        # Verify forces are generated for all modules
        forces = plan["forces"]
        assert len(forces) == 3
        for module in modules:
            assert module in forces
            assert isinstance(forces[module], float)

        # Verify coordinated change: forces should reflect the local optimum structure
        # Module A and B should have forces pushing them away from each other (negative interaction)
        # Module C should have forces pulling it toward A and B (positive interactions)
        assert forces["module_a"] != 0.0
        assert forces["module_b"] != 0.0
        assert forces["module_c"] != 0.0

        # Verify that forces are within reasonable magnitude
        assert abs(forces["module_a"]) < 1.0
        assert abs(forces["module_b"]) < 1.0
        assert abs(forces["module_c"]) < 1.0

        # Verify interactions are included in the plan
        assert len(plan["interactions"]) == 6
        for key in interaction_matrix:
            assert key in plan["interactions"]
            assert plan["interactions"][key] == interaction_matrix[key]

        # Verify that the plan represents a coordinated change
        # The forces should be consistent with breaking out of the local optimum
        # Module A and B should have forces that reduce their mutual negative impact
        # Module C should have forces that increase its positive impact on A and B
        assert forces["module_a"] != forces["module_b"]  # Different forces due to different interactions
        assert forces["module_c"] != 0.0  # Module C should be affected

        # Verify equilibrium state matches plan
        assert equilibrium_state["scores"]["module_a"] == 0.90
        assert equilibrium_state["scores"]["module_b"] == 0.90
        assert equilibrium_state["scores"]["module_c"] == 0.70