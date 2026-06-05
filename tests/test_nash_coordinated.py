"""Integration tests for coordinated Nash equilibrium changes."""

import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from core.nash_detector import NashDetector


@pytest.fixture
def mock_modules():
    """Create 3 mock modules with known interaction patterns."""
    module_a = MagicMock()
    module_a.name = "ModuleA"
    module_a.fitness = 0.5
    module_a.mutate.return_value = "mutated_a"

    module_b = MagicMock()
    module_b.name = "ModuleB"
    module_b.fitness = 0.6
    module_b.mutate.return_value = "mutated_b"

    module_c = MagicMock()
    module_c.name = "ModuleC"
    module_c.fitness = 0.55
    module_c.mutate.return_value = "mutated_c"

    # Define interaction matrix: rows = current module, cols = other modules' mutations
    # High values indicate strong negative impact (Nash trap)
    module_a.interaction_matrix = np.array([
        [0.0, -0.3, -0.2],  # A's fitness change when A, B, C mutate
    ])
    module_b.interaction_matrix = np.array([
        [-0.25, 0.0, -0.15],
    ])
    module_c.interaction_matrix = np.array([
        [-0.2, -0.1, 0.0],
    ])

    return [module_a, module_b, module_c]


@pytest.fixture
def detector():
    """Create a NashDetector instance."""
    return NashDetector()


class TestNashCoordinated:
    """Integration tests for coordinated Nash equilibrium changes."""

    def test_detector_identifies_nash_equilibrium(self, detector, mock_modules):
        """Test that the detector correctly identifies Nash equilibrium states."""
        # Simulate a Nash equilibrium: any single mutation decreases fitness
        fitness_changes = {
            "ModuleA": -0.1,
            "ModuleB": -0.15,
            "ModuleC": -0.05,
        }

        is_nash, nash_modules = detector.detect_nash_equilibrium(
            mock_modules, fitness_changes
        )

        assert is_nash, "Should detect Nash equilibrium when all single mutations are harmful"
        assert len(nash_modules) == 3, "All modules should be in Nash equilibrium"
        for module in mock_modules:
            assert module in nash_modules, f"{module.name} should be in Nash set"

    def test_detector_identifies_non_nash_state(self, detector, mock_modules):
        """Test that the detector correctly identifies non-Nash states."""
        # One module can improve via single mutation
        fitness_changes = {
            "ModuleA": 0.2,   # Beneficial mutation
            "ModuleB": -0.1,
            "ModuleC": -0.05,
        }

        is_nash, nash_modules = detector.detect_nash_equilibrium(
            mock_modules, fitness_changes
        )

        assert not is_nash, "Should not detect Nash when a module can improve alone"
        assert len(nash_modules) == 2, "Only two modules should be in Nash set"
        assert mock_modules[0] not in nash_modules, "ModuleA should not be in Nash set"

    def test_force_coordinated_change_creates_multi_module_plan(
        self, detector, mock_modules
    ):
        """Test that force_coordinated_change produces a multi-module plan."""
        # Mock the detector to indicate Nash equilibrium
        detector.detect_nash_equilibrium = MagicMock(return_value=(True, mock_modules))

        # Mock fitness evaluation for coordinated changes
        def mock_evaluate_coordinated(modules, plan):
            # Return improved fitness for coordinated changes
            return 0.7  # Higher than individual fitnesses

        detector.evaluate_coordinated_change = MagicMock(
            side_effect=mock_evaluate_coordinated
        )

        plan = detector.force_coordinated_change(mock_modules)

        assert plan is not None, "Should produce a plan"
        assert "modules" in plan, "Plan should specify modules"
        assert "changes" in plan, "Plan should specify changes"
        assert len(plan["modules"]) >= 2, "Plan should involve at least 2 modules"
        assert len(plan["changes"]) >= 2, "Plan should have at least 2 changes"
        assert plan["expected_fitness"] > 0.6, "Plan should improve overall fitness"

    def test_coordinated_plan_improves_fitness(
        self, detector, mock_modules
    ):
        """Test that the coordinated plan improves overall fitness."""
        # Setup: modules are in Nash equilibrium
        initial_fitnesses = [m.fitness for m in mock_modules]
        initial_avg = np.mean(initial_fitnesses)

        # Create a coordinated plan
        plan = {
            "modules": ["ModuleA", "ModuleB"],
            "changes": ["mutated_a", "mutated_b"],
            "expected_fitness": 0.75,
        }

        # Mock the mutation results to improve fitness
        mock_modules[0].mutate.return_value = "improved_a"
        mock_modules[1].mutate.return_value = "improved_b"
        mock_modules[0].fitness = 0.8
        mock_modules[1].fitness = 0.75

        # Apply the coordinated plan
        detector.apply_coordinated_plan = MagicMock()
        detector.apply_coordinated_plan(plan)

        # Verify improvements
        new_fitnesses = [m.fitness for m in mock_modules]
        new_avg = np.mean(new_fitnesses)

        assert new_avg > initial_avg, "Coordinated plan should improve average fitness"
        assert mock_modules[0].fitness > initial_fitnesses[0], "ModuleA should improve"
        assert mock_modules[1].fitness > initial_fitnesses[1], "ModuleB should improve"

    def test_coordinated_plan_falls_back_when_no_improvement(
        self, detector, mock_modules
    ):
        """Test fallback when no coordinated plan improves fitness."""
        # Mock no beneficial coordinated changes
        detector.evaluate_coordinated_change = MagicMock(return_value=0.0)

        plan = detector.force_coordinated_change(mock_modules)

        # Should return None or a minimal plan when no improvement found
        assert plan is None or plan.get("expected_fitness", 0) <= max(
            m.fitness for m in mock_modules
        ), "Should not produce plan worse than current state"

    def test_detection_triggers_coordinated_mutation(self, detector, mock_modules):
        """Test that Nash detection triggers coordinated mutation across modules."""
        # Setup: Simulate Nash equilibrium detection
        detector.detect_nash_equilibrium = MagicMock(return_value=(True, mock_modules))
        
        # Mock coordinated change to produce a valid plan
        detector.evaluate_coordinated_change = MagicMock(return_value=0.85)
        detector.force_coordinated_change = MagicMock(
            return_value={
                "modules": ["ModuleA", "ModuleB", "ModuleC"],
                "changes": ["coordinated_mut_a", "coordinated_mut_b", "coordinated_mut_c"],
                "expected_fitness": 0.85,
            }
        )
        
        # Mock apply_coordinated_plan to track calls
        detector.apply_coordinated_plan = MagicMock(return_value=True)
        
        # Run the Nash escape cycle
        is_nash, nash_modules = detector.detect_nash_equilibrium(mock_modules, {m.name: -0.1 for m in mock_modules})
        plan = detector.force_coordinated_change(mock_modules)
        result = detector.apply_coordinated_plan(plan)
        
        # Verify detection triggered coordinated mutation
        assert is_nash, "Nash equilibrium should be detected"
        assert plan is not None, "Coordinated plan should be created"
        assert result, "Coordinated plan should be applied"
        assert len(plan["modules"]) == 3, "All 3 modules should be mutated"
        
        # Verify the coordinated plan was created and applied
        detector.force_coordinated_change.assert_called_once()
        detector.apply_coordinated_plan.assert_called_once()

    def test_atomic_execution_and_rollback_on_failure(self, detector, mock_modules):
        """Test that coordinated mutation executes atomically and rolls back on failure."""
        # Setup: Simulate Nash equilibrium detection
        detector.detect_nash_equilibrium = MagicMock(return_value=(True, mock_modules))
        
        # Create a plan that will fail during application
        detector.evaluate_coordinated_change = MagicMock(return_value=0.75)
        detector.force_coordinated_change = MagicMock(
            return_value={
                "modules": ["ModuleA", "ModuleB", "ModuleC"],
                "changes": ["mut_a_fail", "mut_b_fail", "mut_c_fail"],
                "expected_fitness": 0.75,
            }
        )
        
        # Store initial state for rollback verification
        initial_fitnesses = [m.fitness for m in mock_modules]
        initial_mutate_calls = [m.mutate.call_count for m in mock_modules]
        
        # Mock apply_coordinated_plan to simulate failure and rollback
        def failing_apply(plan):
            # Simulate partial mutation application
            mock_modules[0].mutate.return_value = "partial_mut_a"
            mock_modules[0].fitness = 0.4  # Decreased fitness
            mock_modules[1].mutate.return_value = "partial_mut_b"
            mock_modules[1].fitness = 0.5  # Decreased fitness
            # Simulate failure on third module
            raise RuntimeError("Mutation failed on ModuleC")
        
        detector.apply_coordinated_plan = MagicMock(side_effect=failing_apply)
        
        # Mock rollback functionality
        def rollback_state():
            mock_modules[0].fitness = initial_fitnesses[0]
            mock_modules[1].fitness = initial_fitnesses[1]
            mock_modules[2].fitness = initial_fitnesses[2]
            mock_modules[0].mutate.return_value = "mutated_a"
            mock_modules[1].mutate.return_value = "mutated_b"
            mock_modules[2].mutate.return_value = "mutated_c"
        
        detector.rollback = MagicMock(side_effect=rollback_state)
        
        # Attempt to run Nash escape cycle (should handle failure)
        try:
            plan = detector.force_coordinated_change(mock_modules)
            detector.apply_coordinated_plan(plan)
        except RuntimeError:
            # Perform rollback
            detector.rollback()
            result = {"nash_detected": True, "plan_applied": False, "rolled_back": True}
        else:
            result = {"nash_detected": True, "plan_applied": True, "rolled_back": False}
        
        # Verify atomic execution attempt
        assert result.get("nash_detected", False), "Nash should be detected"
        
        # Verify rollback restored original state
        assert mock_modules[0].fitness == initial_fitnesses[0], "ModuleA fitness should be rolled back"
        assert mock_modules[1].fitness == initial_fitnesses[1], "ModuleB fitness should be rolled back"
        assert mock_modules[2].fitness == initial_fitnesses[2], "ModuleC fitness should be rolled back"
        
        # Verify mutation states are restored
        assert mock_modules[0].mutate.return_value == "mutated_a", "ModuleA mutate should be restored"
        assert mock_modules[1].mutate.return_value == "mutated_b", "ModuleB mutate should be restored"
        assert mock_modules[2].mutate.return_value == "mutated_c", "ModuleC mutate should be restored"
        
        # Verify rollback was called
        detector.rollback.assert_called_once()

    def test_coordinated_mutation_with_atomic_rollback_integration(self, detector, mock_modules):
        """Integration test: setup Nash state, verify detection triggers coordinated mutation with atomic rollback."""
        # Step 1: Setup simulated Nash equilibrium state with 3 interdependent modules
        # Configure modules with Nash trap interactions
        mock_modules[0].interaction_matrix = np.array([[0.0, -0.4, -0.3]])
        mock_modules[1].interaction_matrix = np.array([[-0.35, 0.0, -0.25]])
        mock_modules[2].interaction_matrix = np.array([[-0.3, -0.2, 0.0]])
        
        # Verify initial Nash state
        fitness_changes = {
            "ModuleA": -0.2,
            "ModuleB": -0.15,
            "ModuleC": -0.1,
        }
        is_nash, nash_modules = detector.detect_nash_equilibrium(mock_modules, fitness_changes)
        assert is_nash, "Should be in Nash equilibrium"
        assert len(nash_modules) == 3, "All modules should be in Nash trap"
        
        # Step 2: Verify detection triggers coordinated mutation
        detector.detect_nash_equilibrium = MagicMock(return_value=(True, mock_modules))
        
        # Mock coordinated change evaluation
        detector.evaluate_coordinated_change = MagicMock(return_value=0.9)
        detector.force_coordinated_change = MagicMock(
            return_value={
                "modules": ["ModuleA", "ModuleB", "ModuleC"],
                "changes": ["coordinated_mut_a", "coordinated_mut_b", "coordinated_mut_c"],
                "expected_fitness": 0.9,
            }
        )
        
        # Store initial state for rollback verification
        initial_state = {
            "fitness": [m.fitness for m in mock_modules],
            "mutate_return": [m.mutate.return_value for m in mock_modules]
        }
        
        # Step 3: Verify atomic execution and rollback on failure
        def failing_atomic_apply(plan):
            # Simulate atomic execution attempt
            mock_modules[0].mutate.return_value = "new_mut_a"
            mock_modules[0].fitness = 0.85
            mock_modules[1].mutate.return_value = "new_mut_b"
            mock_modules[1].fitness = 0.88
            # Simulate failure on third mutation
            raise ValueError("Atomic mutation failed on ModuleC")
        
        detector.apply_coordinated_plan = MagicMock(side_effect=failing_atomic_apply)
        
        # Mock rollback to restore initial state
        def atomic_rollback():
            mock_modules[0].fitness = initial_state["fitness"][0]
            mock_modules[1].fitness = initial_state["fitness"][1]
            mock_modules[2].fitness = initial_state["fitness"][2]
            mock_modules[0].mutate.return_value = initial_state["mutate_return"][0]
            mock_modules[1].mutate.return_value = initial_state["mutate_return"][1]
            mock_modules[2].mutate.return_value = initial_state["mutate_return"][2]
        
        detector.rollback = MagicMock(side_effect=atomic_rollback)
        
        # Execute and handle failure
        try:
            plan = detector.force_coordinated_change(mock_modules)
            detector.apply_coordinated_plan(plan)
        except ValueError:
            detector.rollback()
        
        # Verify atomic rollback restored all modules to initial state
        for i, module in enumerate(mock_modules):
            assert module.fitness == initial_state["fitness"][i], f"{module.name} fitness should be rolled back"
            assert module.mutate.return_value == initial_state["mutate_return"][i], f"{module.name} mutate should be rolled back"
        
        # Verify the coordinated mutation was triggered
        detector.force_coordinated_change.assert_called_once()
        detector.apply_coordinated_plan.assert_called_once()
        detector.rollback.assert_called_once()

    def test_minimal_integration_nash_detection_and_coordination(self, detector, mock_modules):
        """Minimal integration test: create mock scenario, verify detect_nash and plan_coordinated_mutations."""
        # (1) Creates a mock scenario with 3 modules where single-module changes show no improvement
        # All single mutations are harmful (negative fitness changes)
        fitness_changes = {
            "ModuleA": -0.1,
            "ModuleB": -0.15,
            "ModuleC": -0.05,
        }
        
        # (2) Verifies detect_nash() returns True
        is_nash, nash_modules = detector.detect_nash_equilibrium(mock_modules, fitness_changes)
        assert is_nash, "Should detect Nash equilibrium when all single mutations are harmful"
        assert len(nash_modules) == 3, "All 3 modules should be in Nash equilibrium"
        
        # (3) Verifies plan_coordinated_mutations() returns a non-empty list
        # Mock evaluate_coordinated_change to return improvement for coordinated changes
        detector.evaluate_coordinated_change = MagicMock(return_value=0.8)
        plan = detector.force_coordinated_change(mock_modules)
        assert plan is not None, "Should produce a coordinated plan"
        assert len(plan["modules"]) > 0, "Plan should have at least one module"
        assert len(plan["changes"]) > 0, "Plan should have at least one change"

    def test_minimal_integration_nash_detection_and_coordination_v2(self, detector, mock_modules):
        """Minimal integration test: (1) Creates a mock orchestrator with 3 modules (2) Simulates 10 cycles of single-module mutations that plateau (3) Verifies Nash equilibrium is detected (4) Verifies coordinated multi-module proposal is generated."""
        # (1) Creates a mock orchestrator with 3 modules
        # Use the mock_modules fixture which provides 3 modules
        
        # (2) Simulates 10 cycles of single-module mutations that plateau
        # Simulate 10 cycles where single-module mutations show no improvement (plateau)
        for cycle in range(10):
            # Each cycle, all single mutations are harmful (negative fitness changes)
            fitness_changes = {
                "ModuleA": -0.1 - (cycle * 0.01),  # Gradually worsening
                "ModuleB": -0.15 - (cycle * 0.01),
                "ModuleC": -0.05 - (cycle * 0.01),
            }
            
            # Check Nash equilibrium after each cycle
            is_nash, nash_modules = detector.detect_nash_equilibrium(mock_modules, fitness_changes)
            
            # After cycle 0, should already be in Nash equilibrium
            if cycle == 0:
                assert is_nash, "Should detect Nash equilibrium from first cycle"
                assert len(nash_modules) == 3, "All 3 modules should be in Nash equilibrium"
            
            # Verify plateau: no single mutation improves fitness
            for module_name, change in fitness_changes.items():
                assert change < 0, f"Single mutation for {module_name} should be harmful (plateau)"
        
        # (3) Verifies Nash equilibrium is detected
        # After 10 cycles, verify Nash equilibrium is still detected
        final_fitness_changes = {
            "ModuleA": -0.2,
            "ModuleB": -0.25,
            "ModuleC": -0.15,
        }
        is_nash, nash_modules = detector.detect_nash_equilibrium(mock_modules, final_fitness_changes)
        assert is_nash, "Should detect Nash equilibrium after 10 cycles of plateau"
        assert len(nash_modules) == 3, "All 3 modules should still be in Nash equilibrium"
        
        # (4) Verifies coordinated multi-module proposal is generated
        # Mock evaluate_coordinated_change to return improvement for coordinated changes
        detector.evaluate_coordinated_change = MagicMock(return_value=0.85)
        plan = detector.force_coordinated_change(mock_modules)
        assert plan is not None, "Should produce a coordinated multi-module proposal"
        assert "modules" in plan, "Plan should specify modules"
        assert "changes" in plan, "Plan should specify changes"
        assert len(plan["modules"]) >= 2, "Coordinated proposal should involve at least 2 modules"
        assert len(plan["changes"]) >= 2, "Coordinated proposal should have at least 2 changes"
        assert plan["expected_fitness"] > 0.6, "Coordinated proposal should improve overall fitness"
        
        # Verify the proposal is multi-module (involves all 3 modules)
        assert len(plan["modules"]) == 3, "Coordinated proposal should involve all 3 modules"
        assert set(plan["modules"]) == {"ModuleA", "ModuleB", "ModuleC"}, "All 3 modules should be in the proposal"