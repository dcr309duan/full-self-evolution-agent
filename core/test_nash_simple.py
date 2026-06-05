from core.nash_detector import NashEquilibriumDetector

def test_nash_simple():
    # (1) Instantiate detector
    detector = NashEquilibriumDetector()

    # (2) Track module interactions
    detector.record_interaction("module_a", "module_b", "request_data", success=True)
    detector.record_interaction("module_b", "module_c", "send_update", success=True)
    detector.record_interaction("module_c", "module_a", "confirm_receipt", success=True)

    # (3) Detect equilibrium after repeated no-improvement
    # Simulate multiple rounds with no improvement
    for _ in range(5):
        detector.record_interaction("module_a", "module_b", "request_data", success=True)
        detector.record_interaction("module_b", "module_c", "send_update", success=True)
        detector.record_interaction("module_c", "module_a", "confirm_receipt", success=True)

    equilibrium = detector.detect_equilibrium()
    assert equilibrium is not None, "Expected equilibrium to be detected"
    assert equilibrium["state"] == "stable", f"Expected stable equilibrium, got {equilibrium['state']}"

    # (4) Generate coordinated change plan
    change_plan = detector.generate_coordinated_change()
    assert change_plan is not None, "Expected a change plan to be generated"
    assert "actions" in change_plan, "Change plan should contain actions"
    assert len(change_plan["actions"]) > 0, "Change plan should have at least one action"

    print("All tests passed!")