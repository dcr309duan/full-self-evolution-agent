import unittest
from ecology_pressure_engine import EcologyPressureEngine

class TestEcologyPressureEngine(unittest.TestCase):
    def setUp(self):
        self.engine = EcologyPressureEngine()

    def test_registry_starts_empty(self):
        """Test that the pressure registry is initially empty."""
        self.assertEqual(len(self.engine.list_pressures()), 0)

    def test_add_pressure(self):
        """Test that adding a pressure increases the registry count."""
        self.engine.add_pressure("test_pressure", lambda ctx: True)
        self.assertEqual(len(self.engine.list_pressures()), 1)

    def test_evaluate_pressures_returns_dict(self):
        """Test that evaluate_pressures returns a dict with pass/fail for each pressure."""
        self.engine.add_pressure("passing_pressure", lambda ctx: True)
        self.engine.add_pressure("failing_pressure", lambda ctx: False)
        results = self.engine.evaluate_pressures({})
        self.assertIsInstance(results, dict)
        self.assertIn("passing_pressure", results)
        self.assertIn("failing_pressure", results)
        self.assertTrue(results["passing_pressure"])
        self.assertFalse(results["failing_pressure"])

if __name__ == "__main__":
    unittest.main()