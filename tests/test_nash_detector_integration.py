import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.nash_detector_and_forcer import NashDetector

def test_nash_detector_integration():
    """Integration test for NashDetector: simulates 6 cycles of no-improvement
    single-module mutations, verifies detector triggers multi-module mode,
    and verifies a multi-module mutation plan is generated."""
    
    # Initialize detector with threshold of 5 cycles
    detector = NashDetector(threshold=5)
    
    # Simulate 6 cycles of no-improvement single-module mutations
    for i in range(6):
        detector.record_cycle("single_module", improved=False)
    
    # Verify detector triggers multi-module mode
    assert detector.is_in_nash(), "Detector should trigger after 6 no-improvement cycles"
    
    # Verify multi-module mode is active
    assert detector.multi_module_mode, "Multi-module mode should be active"
    
    # Generate a multi-module mutation plan
    plan = detector.generate_multi_module_plan()
    
    # Verify plan is generated and contains expected structure
    assert plan is not None, "Multi-module plan should not be None"
    assert "modules" in plan, "Plan should contain 'modules' key"
    assert len(plan["modules"]) > 0, "Plan should have at least one module"
    assert "description" in plan, "Plan should contain a description"
    
    # Verify plan modules are different from single-module
    assert plan["modules"] != ["single_module"], "Plan modules should differ from single-module"
    
    print("All integration tests passed for NashDetector.")

if __name__ == "__main__":
    test_nash_detector_integration()