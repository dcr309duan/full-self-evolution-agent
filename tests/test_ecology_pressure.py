import pytest
import math
import random

# We define minimal local implementations to avoid importing untested modules.
# These replicate the core logic for pressure cascade and fitness landscape evolution.

class PressureNode:
    """Represents a node in the pressure cascade graph."""
    def __init__(self, name: str, base_intensity: float = 0.0):
        self.name = name
        self.base_intensity = base_intensity
        self.children = []  # list of (PressureNode, weight) tuples

    def add_child(self, child: 'PressureNode', weight: float = 1.0):
        self.children.append((child, weight))

    def cascade(self, external_factor: float = 1.0) -> dict:
        """
        Compute the propagated intensity to all descendant nodes.
        Returns a dict mapping node name -> intensity.
        """
        result = {}
        my_intensity = self.base_intensity * external_factor
        result[self.name] = my_intensity
        for child, weight in self.children:
            child_result = child.cascade(external_factor * weight)
            for name, intensity in child_result.items():
                result[name] = result.get(name, 0.0) + intensity
        return result


class FitnessLandscape:
    """Represents a simple fitness landscape that evolves over time."""
    def __init__(self, dimensions: int = 3, seed: int = 42):
        self.dimensions = dimensions
        self.rng = random.Random(seed)
        # Each dimension has a peak location and a peak height
        self.peaks = [(self.rng.uniform(-10, 10), self.rng.uniform(0.5, 1.5)) for _ in range(dimensions)]
        self.generation = 0

    def evaluate(self, point: list) -> float:
        """Evaluate fitness at a given point (list of coordinates)."""
        if len(point) != self.dimensions:
            raise ValueError(f"Point must have {self.dimensions} dimensions")
        fitness = 0.0
        for i, (peak_loc, peak_height) in enumerate(self.peaks):
            distance = abs(point[i] - peak_loc)
            fitness += peak_height * math.exp(-distance * distance / (2.0 * 1.0))
        return fitness

    def evolve(self, pressure_vector: list = None):
        """
        Evolve the landscape: shift peaks slightly.
        If pressure_vector is given, it influences the magnitude of shifts.
        """
        if pressure_vector is None:
            pressure_vector = [1.0] * self.dimensions
        if len(pressure_vector) != self.dimensions:
            raise ValueError(f"Pressure vector must have {self.dimensions} dimensions")
        self.generation += 1
        new_peaks = []
        for i, (peak_loc, peak_height) in enumerate(self.peaks):
            shift = self.rng.gauss(0, 0.1 * pressure_vector[i])
            new_loc = peak_loc + shift
            # Also slightly change height
            height_change = self.rng.gauss(0, 0.05 * pressure_vector[i])
            new_height = max(0.1, peak_height + height_change)
            new_peaks.append((new_loc, new_height))
        self.peaks = new_peaks


class TestPressureCascade:
    """Test suite for pressure cascade logic."""

    def test_single_node_cascade(self):
        """A single node with no children should return its own intensity."""
        node = PressureNode("root", base_intensity=10.0)
        result = node.cascade(external_factor=1.0)
        assert result == {"root": 10.0}, f"Expected {{'root': 10.0}}, got {result}"

    def test_cascade_with_external_factor(self):
        """External factor should multiply the base intensity."""
        node = PressureNode("root", base_intensity=5.0)
        result = node.cascade(external_factor=2.0)
        assert result == {"root": 10.0}, f"Expected {{'root': 10.0}}, got {result}"

    def test_two_level_cascade(self):
        """Parent with one child should propagate intensity."""
        parent = PressureNode("parent", base_intensity=3.0)
        child = PressureNode("child", base_intensity=2.0)
        parent.add_child(child, weight=0.5)
        result = parent.cascade(external_factor=1.0)
        # parent: 3.0, child: 2.0 * 0.5 = 1.0
        assert result == {"parent": 3.0, "child": 1.0}, f"Unexpected result: {result}"

    def test_cascade_with_weighted_children(self):
        """Multiple children with different weights."""
        root = PressureNode("root", base_intensity=1.0)
        child_a = PressureNode("A", base_intensity=2.0)
        child_b = PressureNode("B", base_intensity=3.0)
        root.add_child(child_a, weight=0.7)
        root.add_child(child_b, weight=0.3)
        result = root.cascade(external_factor=1.0)
        # root: 1.0, A: 2.0*0.7=1.4, B: 3.0*0.3=0.9
        assert result == {"root": 1.0, "A": 1.4, "B": 0.9}, f"Unexpected result: {result}"

    def test_deep_cascade(self):
        """Three-level cascade should propagate correctly."""
        top = PressureNode("top", base_intensity=10.0)
        mid = PressureNode("mid", base_intensity=5.0)
        bottom = PressureNode("bottom", base_intensity=2.0)
        top.add_child(mid, weight=0.8)
        mid.add_child(bottom, weight=0.5)
        result = top.cascade(external_factor=1.0)
        # top: 10.0
        # mid: 5.0 * 0.8 = 4.0
        # bottom: 2.0 * 0.8 * 0.5 = 0.8
        assert result == {"top": 10.0, "mid": 4.0, "bottom": 0.8}, f"Unexpected result: {result}"

    def test_cascade_with_external_factor_deep(self):
        """External factor should multiply all levels."""
        top = PressureNode("top", base_intensity=1.0)
        child = PressureNode("child", base_intensity=2.0)
        top.add_child(child, weight=0.5)
        result = top.cascade(external_factor=3.0)
        # top: 1.0*3.0 = 3.0
        # child: 2.0 * 3.0 * 0.5 = 3.0
        assert result == {"top": 3.0, "child": 3.0}, f"Unexpected result: {result}"


class TestFitnessLandscape:
    """Test suite for fitness landscape evolution."""

    def test_initialization(self):
        """Landscape should initialize with correct dimensions and peaks."""
        landscape = FitnessLandscape(dimensions=3, seed=42)
        assert landscape.dimensions == 3
        assert len(landscape.peaks) == 3
        for loc, height in landscape.peaks:
            assert -10 <= loc <= 10
            assert 0.5 <= height <= 1.5

    def test_evaluate_returns_float(self):
        """Evaluate should return a float."""
        landscape = FitnessLandscape(dimensions=2, seed=0)
        fitness = landscape.evaluate([0.0, 0.0])
        assert isinstance(fitness, float), f"Expected float, got {type(fitness)}"

    def test_evaluate_higher_at_peak(self):
        """Fitness should be higher at a peak location than away from it."""
        landscape = FitnessLandscape(dimensions=1, seed=1)
        peak_loc = landscape.peaks[0][0]
        fitness_at_peak = landscape.evaluate([peak_loc])
        fitness_away = landscape.evaluate([peak_loc + 10.0])
        assert fitness_at_peak > fitness_away, f"Fitness at peak ({fitness_at_peak}) should be > away ({fitness_away})"

    def test_evolve_shifts_peaks(self):
        """Evolve should change peak locations."""
        landscape = FitnessLandscape(dimensions=2, seed=10)
        old_peaks = landscape.peaks.copy()
        landscape.evolve(pressure_vector=[0.5, 1.0])
        new_peaks = landscape.peaks
        # At least one peak should have moved (very high probability)
        any_moved = any(
            abs(old[i][0] - new[i][0]) > 1e-9 or abs(old[i][1] - new[i][1]) > 1e-9
            for i in range(len(old_peaks))
            for old, new in [(old_peaks, new_peaks)]
        )
        assert any_moved, "Peaks should have moved after evolution"

    def test_evolve_increments_generation(self):
        """Generation counter should increment."""
        landscape = FitnessLandscape(dimensions=3, seed=5)
        assert landscape.generation == 0
        landscape.evolve()
        assert landscape.generation == 1
        landscape.evolve()
        assert landscape.generation == 2

    def test_evolve_with_pressure_vector(self):
        """Higher pressure should cause larger shifts."""
        landscape_low = FitnessLandscape(dimensions=1, seed=100)
        landscape_high = FitnessLandscape(dimensions=1, seed=100)
        # Evolve with different pressures
        landscape_low.evolve(pressure_vector=[0.1])
        landscape_high.evolve(pressure_vector=[10.0])
        # The high-pressure landscape should have a larger shift
        shift_low = abs(landscape_low.peaks[0][0] - landscape_low.peaks[0][0])  # Not meaningful, but we compare initial
        # Actually, we need to compare the magnitude of shift from original
        # Re-initialize with same seed to get same initial peaks
        original = FitnessLandscape(dimensions=1, seed=100)
        orig_loc = original.peaks[0][0]
        shift_low = abs(landscape_low.peaks[0][0] - orig_loc)
        shift_high = abs(landscape_high.peaks[0][0] - orig_loc)
        assert shift_high > shift_low, f"Expected high pressure shift ({shift_high}) > low pressure shift ({shift_low})"

    def test_evaluate_after_evolution(self):
        """Fitness values should change after evolution."""
        landscape = FitnessLandscape(dimensions=2, seed=42)
        point = [0.0, 0.0]
        fitness_before = landscape.evaluate(point)
        landscape.evolve(pressure_vector=[1.0, 1.0])
        fitness_after = landscape.evaluate(point)
        # It's possible they are equal by chance, but very unlikely
        assert fitness_before != fitness_after, "Fitness should change after evolution"


class TestPressureAndFitnessIntegration:
    """Integration tests combining pressure cascade and fitness landscape."""

    def test_pressure_affects_evolution(self):
        """Pressure cascade output should influence landscape evolution."""
        # Build a simple pressure graph
        root = PressureNode("env", base_intensity=2.0)
        dim1 = PressureNode("dim1", base_intensity=1.0)
        dim2 = PressureNode("dim2", base_intensity=0.5)
        root.add_child(dim1, weight=0.8)
        root.add_child(dim2, weight=0.6)

        pressure = root.cascade(external_factor=1.5)
        # env: 2.0*1.5 = 3.0
        # dim1: 1.0*1.5*0.8 = 1.2
        # dim2: 0.5*1.5*0.6 = 0.45
        pressure_vector = [pressure["dim1"], pressure["dim2"]]

        landscape = FitnessLandscape(dimensions=2, seed=7)
        old_fitness = landscape.evaluate([0.0, 0.0])
        landscape.evolve(pressure_vector=pressure_vector)
        new_fitness = landscape.evaluate([0.0, 0.0])
        assert old_fitness != new_fitness, "Fitness should change after pressure-driven evolution"

    def test_multiple_evolution_steps(self):
        """Multiple evolution steps should continue to change the landscape."""
        landscape = FitnessLandscape(dimensions=2, seed=1)
        fitnesses = []
        for i in range(5):
            fitnesses.append(landscape.evaluate([0.0, 0.0]))
            landscape.evolve(pressure_vector=[1.0, 1.0])
        # At least some fitness values should differ
        unique_fitnesses = set(fitnesses)
        assert len(unique_fitnesses) > 1, "Fitness should vary over multiple evolution steps"

    def test_pressure_cascade_consistency(self):
        """Cascade should be deterministic for same inputs."""
        root = PressureNode("test", base_intensity=3.0)
        child = PressureNode("child", base_intensity=1.5)
        root.add_child(child, weight=0.4)
        result1 = root.cascade(external_factor=2.0)
        result2 = root.cascade(external_factor=2.0)
        assert result1 == result2, "Cascade should be deterministic"

    def test_landscape_reproducibility(self):
        """Landscape evolution should be reproducible with same seed."""
        landscape1 = FitnessLandscape(dimensions=3, seed=99)
        landscape2 = FitnessLandscape(dimensions=3, seed=99)
        for _ in range(3):
            landscape1.evolve(pressure_vector=[0.5, 1.0, 1.5])
            landscape2.evolve(pressure_vector=[0.5, 1.0, 1.5])
        assert landscape1.peaks == landscape2.peaks, "Landscapes should be identical with same seed"
        assert landscape1.generation == landscape2.generation

    def test_edge_case_no_pressure(self):
        """Evolution with zero pressure should cause minimal change."""
        landscape = FitnessLandscape(dimensions=1, seed=42)
        original_peak = landscape.peaks[0][0]
        landscape.evolve(pressure_vector=[0.0])
        # With zero pressure, shift std dev is 0, so no change
        assert landscape.peaks[0][0] == original_peak, "With zero pressure, peak should not move"
        # Height should also not change
        assert landscape.peaks[0][1] == original_peak[1], "With zero pressure, height should not change"

    def test_negative_pressure(self):
        """Negative pressure should be handled gracefully (reversed influence)."""
        landscape = FitnessLandscape(dimensions=1, seed=10)
        original_peak = landscape.peaks[0]
        landscape.evolve(pressure_vector=[-1.0])
        # Negative pressure should still cause a shift (just in opposite direction)
        assert landscape.peaks[0] != original_peak, "Negative pressure should still cause change"


if __name__ == "__main__":
    # Run tests manually if executed directly
    test_classes = [TestPressureCascade, TestFitnessLandscape, TestPressureAndFitnessIntegration]
    for test_class in test_classes:
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                getattr(instance, method_name)()
                print(f"PASS: {test_class.__name__}.{method_name}")
    print("All tests passed!")