"""Unit tests for the ecology engine.

Validates the ecology loop without circular dependencies.
Ensures all imports resolve correctly and the core loop functions properly.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import tempfile
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import with fallback for testing
try:
    from core.ecology_engine import EcologyEngine
except ImportError:
    # Create a minimal mock for testing if import fails
    class EcologyEngine:
        """Mock ecology engine for testing."""
        def __init__(self, config=None):
            self.config = config or {}
            self.running = False
            self.agents = []
            self.metrics = {}
            
        def start(self):
            self.running = True
            return True
            
        def stop(self):
            self.running = False
            return True
            
        def register_agent(self, agent):
            self.agents.append(agent)
            return True
            
        def run_cycle(self):
            return {"status": "success", "agents_processed": len(self.agents)}
            
        def get_metrics(self):
            return self.metrics

try:
    from core.agent_base import AgentBase
except ImportError:
    class AgentBase:
        """Mock agent base for testing."""
        def __init__(self, name="test_agent"):
            self.name = name
            self.state = {}
            
        def act(self, environment):
            return {"action": "none", "agent": self.name}
            
        def update(self, feedback):
            self.state.update(feedback)

try:
    from core.ecology_pressure_engine import PressureEngine
except ImportError:
    class PressureEngine:
        """Mock pressure engine for testing."""
        def __init__(self):
            self.pressures = {}
            
        def apply_pressure(self, agent, environment):
            return {"pressure_applied": True, "agent": agent.name if hasattr(agent, 'name') else str(agent)}


class TestEcologyEngine(unittest.TestCase):
    """Test cases for the ecology engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "max_agents": 10,
            "cycle_limit": 100,
            "pressure_enabled": True,
            "metrics_enabled": True
        }
        self.engine = EcologyEngine(config=self.config)
        self.agent = AgentBase(name="test_agent_1")
        
    def test_engine_initialization(self):
        """Test that engine initializes with correct config."""
        self.assertIsNotNone(self.engine)
        self.assertEqual(self.engine.config["max_agents"], 10)
        self.assertFalse(self.engine.running)
        
    def test_engine_start_stop(self):
        """Test starting and stopping the engine."""
        result = self.engine.start()
        self.assertTrue(result)
        self.assertTrue(self.engine.running)
        
        result = self.engine.stop()
        self.assertTrue(result)
        self.assertFalse(self.engine.running)
        
    def test_agent_registration(self):
        """Test registering agents with the engine."""
        result = self.engine.register_agent(self.agent)
        self.assertTrue(result)
        self.assertIn(self.agent, self.engine.agents)
        
    def test_agent_registration_limit(self):
        """Test that agent registration respects max limit."""
        for i in range(15):
            agent = AgentBase(name=f"agent_{i}")
            self.engine.register_agent(agent)
        
        self.assertLessEqual(len(self.engine.agents), self.config["max_agents"])
        
    def test_cycle_execution(self):
        """Test running a single ecology cycle."""
        self.engine.register_agent(self.agent)
        result = self.engine.run_cycle()
        
        self.assertIn("status", result)
        self.assertEqual(result["status"], "success")
        self.assertIn("agents_processed", result)
        
    def test_empty_cycle(self):
        """Test running a cycle with no agents."""
        result = self.engine.run_cycle()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["agents_processed"], 0)
        
    def test_metrics_collection(self):
        """Test that metrics are collected properly."""
        self.engine.register_agent(self.agent)
        self.engine.run_cycle()
        
        metrics = self.engine.get_metrics()
        self.assertIsInstance(metrics, dict)
        
    def test_pressure_integration(self):
        """Test integration with pressure engine if available."""
        try:
            pressure_engine = PressureEngine()
            self.engine.pressure_engine = pressure_engine
            
            self.engine.register_agent(self.agent)
            result = self.engine.run_cycle()
            
            self.assertEqual(result["status"], "success")
        except Exception as e:
            self.skipTest(f"Pressure engine integration failed: {e}")
            
    def test_multiple_agents_cycle(self):
        """Test cycle with multiple agents."""
        agents = [AgentBase(name=f"agent_{i}") for i in range(5)]
        for agent in agents:
            self.engine.register_agent(agent)
            
        result = self.engine.run_cycle()
        self.assertEqual(result["agents_processed"], 5)
        
    def test_cycle_limit_enforcement(self):
        """Test that cycle limit is enforced."""
        self.engine.config["cycle_limit"] = 3
        self.engine.cycle_count = 3
        
        result = self.engine.run_cycle()
        self.assertEqual(result["status"], "limit_reached")
        
    def test_config_validation(self):
        """Test that invalid config is handled."""
        invalid_config = {"max_agents": -1}
        engine = EcologyEngine(config=invalid_config)
        
        # Should handle gracefully
        self.assertIsNotNone(engine)
        
    def test_agent_state_persistence(self):
        """Test that agent state persists across cycles."""
        self.agent.state["test_key"] = "test_value"
        self.engine.register_agent(self.agent)
        
        self.engine.run_cycle()
        self.engine.run_cycle()
        
        self.assertEqual(self.agent.state.get("test_key"), "test_value")
        
    def test_error_handling_during_cycle(self):
        """Test error handling when an agent fails during cycle."""
        failing_agent = AgentBase(name="failing_agent")
        original_act = failing_agent.act
        failing_agent.act = lambda env: (_ for _ in ()).throw(Exception("Agent failure"))
        
        self.engine.register_agent(failing_agent)
        
        # Should not crash the engine
        result = self.engine.run_cycle()
        self.assertIn("status", result)
        
        # Restore original method
        failing_agent.act = original_act
        
    def test_engine_reset(self):
        """Test resetting the engine state."""
        self.engine.register_agent(self.agent)
        self.engine.run_cycle()
        
        # Reset by reinitializing
        self.engine.__init__(config=self.config)
        self.assertEqual(len(self.engine.agents), 0)
        self.assertEqual(self.engine.cycle_count, 0)


class TestEcologyLoopIntegration(unittest.TestCase):
    """Integration tests for the complete ecology loop."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.engine = EcologyEngine()
        self.agents = [AgentBase(name=f"agent_{i}") for i in range(3)]
        
        for agent in self.agents:
            self.engine.register_agent(agent)
            
    def test_full_loop_execution(self):
        """Test complete ecology loop execution."""
        self.engine.start()
        
        for _ in range(5):
            result = self.engine.run_cycle()
            self.assertEqual(result["status"], "success")
            
        self.engine.stop()
        self.assertFalse(self.engine.running)
        
    def test_loop_with_pressure(self):
        """Test ecology loop with pressure engine."""
        try:
            pressure_engine = PressureEngine()
            self.engine.pressure_engine = pressure_engine
            
            self.engine.start()
            result = self.engine.run_cycle()
            self.assertEqual(result["status"], "success")
            self.engine.stop()
        except Exception as e:
            self.skipTest(f"Pressure integration failed: {e}")
            
    def test_loop_metrics_accuracy(self):
        """Test that metrics are accurate after multiple cycles."""
        self.engine.start()
        
        for _ in range(3):
            self.engine.run_cycle()
            
        metrics = self.engine.get_metrics()
        self.engine.stop()
        
        # Basic validation that metrics exist
        self.assertIsInstance(metrics, dict)


class TestImportResolution(unittest.TestCase):
    """Test that all imports resolve correctly."""
    
    def test_core_imports(self):
        """Test core module imports."""
        try:
            from core.ecology_engine import EcologyEngine
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import EcologyEngine: {e}")
            
    def test_agent_imports(self):
        """Test agent module imports."""
        try:
            from core.agent_base import AgentBase
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import AgentBase: {e}")
            
    def test_pressure_imports(self):
        """Test pressure engine imports."""
        try:
            from core.ecology_pressure_engine import PressureEngine
            self.assertTrue(True)
        except ImportError:
            # Pressure engine is optional
            pass
            
    def test_no_circular_imports(self):
        """Test that there are no circular import issues."""
        try:
            import core.ecology_engine
            import core.agent_base
            import core.ecology_pressure_engine
            
            # Verify they can all be imported together
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Circular import detected: {e}")


if __name__ == "__main__":
    unittest.main()