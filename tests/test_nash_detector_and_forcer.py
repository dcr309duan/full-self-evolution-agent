"""Tests for the Nash detector and forcer module.

This test file is self-contained and imports only from
core.nash_detector_and_forcer and standard library modules.
"""

import unittest
from core.nash_detector_and_forcer import (
    detect_nash_equilibrium,
    generate_coordinated_changes,
    NashState,
    NashResult,
    CoordinatedChange,
)


class TestNashState(unittest.TestCase):
    """Tests for the NashState class."""

    def test_empty_state(self):
        """Test creating an empty Nash state."""
        state = NashState(modules={}, scores={})
        self.assertEqual(len(state.modules), 0)
        self.assertEqual(len(state.scores), 0)

    def test_single_module_state(self):
        """Test creating a state with a single module."""
        state = NashState(
            modules={"mod1": {"param": 10}},
            scores={"mod1": 0.85},
        )
        self.assertEqual(state.modules["mod1"]["param"], 10)
        self.assertEqual(state.scores["mod1"], 0.85)

    def test_multi_module_state(self):
        """Test creating a state with multiple modules."""
        state = NashState(
            modules={
                "mod1": {"param": 10},
                "mod2": {"param": 20},
            },
            scores={
                "mod1": 0.85,
                "mod2": 0.75,
            },
        )
        self.assertEqual(len(state.modules), 2)
        self.assertEqual(len(state.scores), 2)


class TestDetectNashEquilibrium(unittest.TestCase):
    """Tests for the detect_nash_equilibrium function."""

    def test_empty_state(self):
        """Test detection on an empty state."""
        state = NashState(modules={}, scores={})
        result = detect_nash_equilibrium(state)
        self.assertIsInstance(result, NashResult)
        self.assertTrue(result.is_nash)
        self.assertEqual(len(result.best_responses), 0)

    def test_single_module_nash(self):
        """Test detection when single module cannot improve."""
        state = NashState(
            modules={"mod1": {"param": 10}},
            scores={"mod1": 1.0},  # Already max score
        )
        result = detect_nash_equilibrium(state)
        self.assertTrue(result.is_nash)
        self.assertEqual(len(result.best_responses), 1)
        self.assertEqual(result.best_responses["mod1"], 0.0)

    def test_single_module_not_nash(self):
        """Test detection when single module can improve."""
        state = NashState(
            modules={"mod1": {"param": 5}},
            scores={"mod1": 0.5},  # Can improve
        )
        result = detect_nash_equilibrium(state)
        self.assertFalse(result.is_nash)
        self.assertIn("mod1", result.best_responses)
        self.assertGreater(result.best_responses["mod1"], 0.0)

    def test_multi_module_nash(self):
        """Test detection when no module can improve unilaterally."""
        state = NashState(
            modules={
                "mod1": {"param": 10},
                "mod2": {"param": 20},
            },
            scores={
                "mod1": 0.95,
                "mod2": 0.90,
            },
        )
        result = detect_nash_equilibrium(state)
        self.assertTrue(result.is_nash)

    def test_multi_module_not_nash(self):
        """Test detection when at least one module can improve."""
        state = NashState(
            modules={
                "mod1": {"param": 10},
                "mod2": {"param": 5},  # Low score, can improve
            },
            scores={
                "mod1": 0.95,
                "mod2": 0.30,
            },
        )
        result = detect_nash_equilibrium(state)
        self.assertFalse(result.is_nash)
        self.assertIn("mod2", result.best_responses)

    def test_all_modules_can_improve(self):
        """Test detection when all modules can improve."""
        state = NashState(
            modules={
                "mod1": {"param": 1},
                "mod2": {"param": 2},
                "mod3": {"param": 3},
            },
            scores={
                "mod1": 0.1,
                "mod2": 0.2,
                "mod3": 0.3,
            },
        )
        result = detect_nash_equilibrium(state)
        self.assertFalse(result.is_nash)
        self.assertEqual(len(result.best_responses), 3)


class TestGenerateCoordinatedChanges(unittest.TestCase):
    """Tests for the generate_coordinated_changes function."""

    def test_empty_state(self):
        """Test generating changes for an empty state."""
        state = NashState(modules={}, scores={})
        changes = generate_coordinated_changes(state)
        self.assertEqual(len(changes), 0)

    def test_single_module(self):
        """Test generating changes for a single module."""
        state = NashState(
            modules={"mod1": {"param": 5}},
            scores={"mod1": 0.5},
        )
        changes = generate_coordinated_changes(state)
        self.assertGreater(len(changes), 0)
        for change in changes:
            self.assertIsInstance(change, CoordinatedChange)
            self.assertIn("mod1", change.module_changes)

    def test_multi_module(self):
        """Test generating coordinated changes for multiple modules."""
        state = NashState(
            modules={
                "mod1": {"param": 5},
                "mod2": {"param": 10},
            },
            scores={
                "mod1": 0.5,
                "mod2": 0.6,
            },
        )
        changes = generate_coordinated_changes(state)
        self.assertGreater(len(changes), 0)
        for change in changes:
            self.assertIsInstance(change, CoordinatedChange)
            # Each change should affect at least one module
            self.assertGreater(len(change.module_changes), 0)

    def test_coordinated_changes_improve_scores(self):
        """Test that coordinated changes improve overall scores."""
        state = NashState(
            modules={
                "mod1": {"param": 5},
                "mod2": {"param": 10},
            },
            scores={
                "mod1": 0.5,
                "mod2": 0.6,
            },
        )
        changes = generate_coordinated_changes(state)
        for change in changes:
            # The change should have a positive expected improvement
            self.assertGreater(change.expected_improvement, 0.0)

    def test_no_improvement_possible(self):
        """Test when no coordinated improvement is possible."""
        state = NashState(
            modules={
                "mod1": {"param": 10},
                "mod2": {"param": 20},
            },
            scores={
                "mod1": 1.0,
                "mod2": 1.0,
            },
        )
        changes = generate_coordinated_changes(state)
        # May still generate changes but with zero expected improvement
        for change in changes:
            self.assertGreaterEqual(change.expected_improvement, 0.0)


class TestIntegration(unittest.TestCase):
    """Integration tests combining detection and forcing."""

    def test_detect_then_force(self):
        """Test full workflow: detect Nash, then generate coordinated changes."""
        # Start with a non-Nash state
        state = NashState(
            modules={
                "mod1": {"param": 5},
                "mod2": {"param": 10},
            },
            scores={
                "mod1": 0.5,
                "mod2": 0.7,
            },
        )

        # Detect Nash
        result = detect_nash_equilibrium(state)
        self.assertFalse(result.is_nash)

        # Generate coordinated changes to break out of non-Nash state
        changes = generate_coordinated_changes(state)
        self.assertGreater(len(changes), 0)

    def test_nash_state_no_changes_needed(self):
        """Test that Nash state requires no coordinated changes."""
        state = NashState(
            modules={
                "mod1": {"param": 10},
                "mod2": {"param": 20},
            },
            scores={
                "mod1": 0.95,
                "mod2": 0.95,
            },
        )

        # Detect Nash
        result = detect_nash_equilibrium(state)
        self.assertTrue(result.is_nash)

        # Generate changes - should have zero or minimal expected improvement
        changes = generate_coordinated_changes(state)
        for change in changes:
            self.assertAlmostEqual(change.expected_improvement, 0.0, places=5)

    def test_large_state(self):
        """Test with a larger number of modules."""
        modules = {f"mod{i}": {"param": i * 10} for i in range(10)}
        scores = {f"mod{i}": 0.5 + (i * 0.05) for i in range(10)}

        state = NashState(modules=modules, scores=scores)
        result = detect_nash_equilibrium(state)
        changes = generate_coordinated_changes(state)

        self.assertIsInstance(result, NashResult)
        self.assertGreater(len(changes), 0)


if __name__ == "__main__":
    unittest.main()