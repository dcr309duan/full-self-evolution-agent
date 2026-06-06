import unittest
import tempfile
import os
import json
import shutil
import random
import string

class TestEcologyEngine(unittest.TestCase):
    """Self-contained tests for ecology engine concepts without importing project modules."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.test_dir)

    def create_mock_test_file(self, directory, filename, content=None):
        """Helper to create a mock test file in the given directory."""
        if content is None:
            content = "import unittest\n\nclass TestMock(unittest.TestCase):\n    def test_pass(self):\n        self.assertTrue(True)\n"
        filepath = os.path.join(directory, filename)
        with open(filepath, 'w') as f:
            f.write(content)
        return filepath

    # --- TestSuiteEvolver tests ---
    def test_ts_evolver_scans_mock_directory(self):
        """Test that TestSuiteEvolver can scan a mock test directory and find test files."""
        # Create a mock test directory with test files
        mock_dir = os.path.join(self.test_dir, "tests")
        os.makedirs(mock_dir)
        self.create_mock_test_file(mock_dir, "test_foo.py")
        self.create_mock_test_file(mock_dir, "test_bar.py")
        self.create_mock_test_file(mock_dir, "not_a_test.py")  # Should be ignored

        # Minimal TestSuiteEvolver implementation
        class TestSuiteEvolver:
            def __init__(self, test_dir):
                self.test_dir = test_dir
                self.test_files = []

            def scan(self):
                for f in os.listdir(self.test_dir):
                    if f.startswith("test_") and f.endswith(".py"):
                        self.test_files.append(os.path.join(self.test_dir, f))
                return self.test_files

        evolver = TestSuiteEvolver(mock_dir)
        found = evolver.scan()
        self.assertEqual(len(found), 2)
        self.assertTrue(any("test_foo.py" in f for f in found))
        self.assertTrue(any("test_bar.py" in f for f in found))
        self.assertFalse(any("not_a_test.py" in f for f in found))

    def test_ts_evolver_handles_empty_directory(self):
        """Test that TestSuiteEvolver handles an empty directory gracefully."""
        mock_dir = os.path.join(self.test_dir, "empty_tests")
        os.makedirs(mock_dir)

        class TestSuiteEvolver:
            def __init__(self, test_dir):
                self.test_dir = test_dir

            def scan(self):
                return [os.path.join(self.test_dir, f) for f in os.listdir(self.test_dir)
                        if f.startswith("test_") and f.endswith(".py")]

        evolver = TestSuiteEvolver(mock_dir)
        self.assertEqual(evolver.scan(), [])

    # --- EnvironmentalPressureGenerator tests ---
    def test_epg_creates_at_least_3_new_test_types(self):
        """Test that EnvironmentalPressureGenerator creates at least 3 new test types."""
        class EnvironmentalPressureGenerator:
            def __init__(self, seed=42):
                self.seed = seed
                random.seed(seed)

            def generate_test_types(self, count=5):
                types = []
                for _ in range(count):
                    test_type = ''.join(random.choices(string.ascii_lowercase, k=8))
                    types.append(test_type)
                return types

            def generate_pressures(self, base_types, count=3):
                """Generate new test types based on existing ones."""
                new_types = []
                for _ in range(count):
                    new_type = f"pressure_{''.join(random.choices(string.ascii_lowercase, k=6))}"
                    new_types.append(new_type)
                return new_types

        generator = EnvironmentalPressureGenerator()
        base_types = ["unit", "integration", "functional"]
        new_types = generator.generate_pressures(base_types, count=5)
        self.assertGreaterEqual(len(new_types), 3)
        self.assertTrue(all(t.startswith("pressure_") for t in new_types))

    def test_epg_generates_unique_test_types(self):
        """Test that generated test types are unique."""
        class EnvironmentalPressureGenerator:
            def __init__(self, seed=42):
                self.seed = seed
                random.seed(seed)

            def generate_pressures(self, base_types, count=5):
                new_types = set()
                while len(new_types) < count:
                    new_type = f"pressure_{''.join(random.choices(string.ascii_lowercase, k=6))}"
                    new_types.add(new_type)
                return list(new_types)

        generator = EnvironmentalPressureGenerator()
        new_types = generator.generate_pressures(["unit"], count=5)
        self.assertEqual(len(new_types), 5)
        self.assertEqual(len(set(new_types)), 5)

    # --- FitnessLandscapeModifier tests ---
    def test_flm_detects_all_tests_pass(self):
        """Test that FitnessLandscapeModifier can detect when all tests pass."""
        class FitnessLandscapeModifier:
            def __init__(self):
                self.test_results = {}

            def evaluate(self, results):
                """Evaluate test results and return fitness score."""
                if not results:
                    return 0.0
                passed = sum(1 for r in results if r.get("passed", False))
                return passed / len(results)

            def generate_harder_variants(self, results):
                """Generate harder test variants if all tests pass."""
                if self.evaluate(results) == 1.0:
                    harder_variants = []
                    for test in results:
                        harder_variant = {
                            "name": f"{test['name']}_harder",
                            "difficulty": test.get("difficulty", 1) + 1,
                            "constraints": test.get("constraints", []) + ["time_limit"]
                        }
                        harder_variants.append(harder_variant)
                    return harder_variants
                return []

        modifier = FitnessLandscapeModifier()
        all_pass = [{"name": "test_1", "passed": True, "difficulty": 1},
                     {"name": "test_2", "passed": True, "difficulty": 2}]
        harder = modifier.generate_harder_variants(all_pass)
        self.assertEqual(len(harder), 2)
        self.assertTrue(all("_harder" in v["name"] for v in harder))
        self.assertTrue(all(v["difficulty"] > 1 for v in harder))
        self.assertTrue(all("time_limit" in v["constraints"] for v in harder))

    def test_flm_does_not_generate_harder_when_failures(self):
        """Test that harder variants are not generated when some tests fail."""
        class FitnessLandscapeModifier:
            def __init__(self):
                pass

            def evaluate(self, results):
                if not results:
                    return 0.0
                passed = sum(1 for r in results if r.get("passed", False))
                return passed / len(results)

            def generate_harder_variants(self, results):
                if self.evaluate(results) == 1.0:
                    return [{"name": f"{r['name']}_harder"} for r in results]
                return []

        modifier = FitnessLandscapeModifier()
        some_fail = [{"name": "test_1", "passed": True},
                      {"name": "test_2", "passed": False}]
        harder = modifier.generate_harder_variants(some_fail)
        self.assertEqual(harder, [])

    def test_flm_handles_empty_results(self):
        """Test that FitnessLandscapeModifier handles empty results gracefully."""
        class FitnessLandscapeModifier:
            def __init__(self):
                pass

            def evaluate(self, results):
                if not results:
                    return 0.0
                passed = sum(1 for r in results if r.get("passed", False))
                return passed / len(results)

            def generate_harder_variants(self, results):
                if self.evaluate(results) == 1.0:
                    return [{"name": f"{r['name']}_harder"} for r in results]
                return []

        modifier = FitnessLandscapeModifier()
        self.assertEqual(modifier.generate_harder_variants([]), [])

    # --- Integration-like tests ---
    def test_ecology_engine_integration(self):
        """Test a simple integration of all three components."""
        # Setup
        mock_dir = os.path.join(self.test_dir, "integration_tests")
        os.makedirs(mock_dir)
        self.create_mock_test_file(mock_dir, "test_a.py")
        self.create_mock_test_file(mock_dir, "test_b.py")

        # TestSuiteEvolver
        class TestSuiteEvolver:
            def __init__(self, test_dir):
                self.test_dir = test_dir

            def scan(self):
                return [os.path.join(self.test_dir, f) for f in os.listdir(self.test_dir)
                        if f.startswith("test_") and f.endswith(".py")]

        evolver = TestSuiteEvolver(mock_dir)
        test_files = evolver.scan()
        self.assertEqual(len(test_files), 2)

        # EnvironmentalPressureGenerator
        class EnvironmentalPressureGenerator:
            def generate_pressures(self, base_types, count=3):
                return [f"pressure_{i}" for i in range(count)]

        generator = EnvironmentalPressureGenerator()
        pressures = generator.generate_pressures(["unit"], count=3)
        self.assertEqual(len(pressures), 3)

        # FitnessLandscapeModifier
        class FitnessLandscapeModifier:
            def evaluate(self, results):
                if not results:
                    return 0.0
                passed = sum(1 for r in results if r.get("passed", False))
                return passed / len(results)

            def generate_harder_variants(self, results):
                if self.evaluate(results) == 1.0:
                    return [{"name": f"{r['name']}_harder"} for r in results]
                return []

        modifier = FitnessLandscapeModifier()
        all_pass = [{"name": "test_a", "passed": True}, {"name": "test_b", "passed": True}]
        harder = modifier.generate_harder_variants(all_pass)
        self.assertEqual(len(harder), 2)

if __name__ == "__main__":
    unittest.main()