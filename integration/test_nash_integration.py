import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.nash_detector import NashDetector
from core.multi_module_forcer import MultiModuleForcer

def test_nash_integration():
    detector = NashDetector()
    forcer = MultiModuleForcer()
    
    for _ in range(5):
        detector.record_interaction()
        forcer.force_multi_module_change()
    
    assert detector.detect_nash() == True, "Nash equilibrium should be detected after 5 cycles"
    plan = forcer.force_multi_module_change()
    assert isinstance(plan, dict), "Plan should be a dictionary"
    assert len(plan) > 0, "Plan should have at least one module change"
    assert "module" in plan, "Plan should specify a module"
    assert "change" in plan, "Plan should specify a change"