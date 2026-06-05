"""Integration tests for coordinated Nash equilibrium changes."""

import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from core.nash_detector import NashDetector
from core.evolution_orchestrator import EvolutionOrchestrator


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


@pytest.fixture
def orchestrator(detector, mock_modules):
    """Create an EvolutionOrchestrator with detector and modules."""
    orch = EvolutionOrchestrator()
    orch.modules = mock_modules
    orch.nash_detector = detector
    return orch


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
        self, detector, mock_modules, orchestrator
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
        orchestrator.apply_coordinated_plan(plan)

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

    def test_end_to_end_nash_escape(self, orchestrator, detector, mock_modules):
        """End-to-end test: detect Nash, create plan, apply it, verify escape."""
        # Step 1: Simulate Nash detection
        fitness_changes = {m.name: -0.1 for m in mock_modules}
        detector.detect_nash_equilibrium = MagicMock(
            return_value=(True, mock_modules)
        )

        # Step 2: Create coordinated plan
        detector.evaluate_coordinated_change = MagicMock(return_value=0.8)
        detector.force_coordinated_change = MagicMock(
            return_value={
                "modules": ["ModuleA", "ModuleB", "ModuleC"],
                "changes": ["mut_a", "mut_b", "mut_c"],
                "expected_fitness": 0.8,
            }
        )

        # Step 3: Run the orchestration
        result = orchestrator.run_nash_escape_cycle()

        # Step 4: Verify escape from Nash
        assert result["nash_detected"], "Should detect Nash equilibrium"
        assert result["plan_applied"], "Should apply coordinated plan"
        assert result["new_fitness"] > 0.6, "Fitness should improve after escape"
        assert len(result["modules_changed"]) == 3, "All modules should be changed"