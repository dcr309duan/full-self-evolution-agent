#!/usr/bin/env python3
"""
Standalone integration test for Nash equilibrium detection and coordinated mutation.
Simulates a multi-module system with improvement cycles.
Usage: python integration_test_nash.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from core.nash_detector import NashEquilibriumDetector
    from core.multi_module_forcer import MultiModuleForcer
except ImportError:
    try:
        from nash_detector import NashEquilibriumDetector
        from multi_module_forcer import MultiModuleForcer
    except ImportError:
        print("ERROR: Could not import nash_detector or multi_module_forcer.")
        print("Ensure they are in the Python path or in the same directory.")
        sys.exit(1)


def simulate_improvement_cycle(detector, forcer, module_name, improvement=True):
    """Simulate one cycle of improvement or stagnation for a module."""
    if improvement:
        detector.record_improvement(module_name)
        print(f"  {module_name}: improvement recorded")
    else:
        detector.record_no_improvement(module_name)
        print(f"  {module_name}: no improvement recorded")


def main():
    print("=" * 60)
    print("Nash Equilibrium Integration Test")
    print("=" * 60)

    # Step 1: Initialize components
    print("\n[Step 1] Initializing NashEquilibriumDetector and MultiModuleForcer...")
    detector = NashEquilibriumDetector()
    forcer = MultiModuleForcer()
    print("  Done.")

    # Define our modules
    modules = ["module_a", "module_b", "module_c"]

    # Step 2: Simulate 5 cycles of single-module improvements
    print("\n[Step 2] Simulating 5 cycles of single-module improvements...")
    for cycle in range(1, 6):
        print(f"  Cycle {cycle}:")
        for module in modules:
            simulate_improvement_cycle(detector, forcer, module, improvement=True)

    # Check state after improvements
    print("\n  State after improvements:")
    for module in modules:
        recent = detector.get_recent_history(module, window=5)
        print(f"    {module}: recent history = {recent}")

    # Step 3: Simulate 3 cycles of no improvement (stagnation)
    print("\n[Step 3] Simulating 3 cycles of no improvement (stagnation)...")
    for cycle in range(1, 4):
        print(f"  Stagnation cycle {cycle}:")
        for module in modules:
            simulate_improvement_cycle(detector, forcer, module, improvement=False)

    # Step 4: Verify Nash equilibrium is detected
    print("\n[Step 4] Verifying Nash equilibrium detection...")
    is_nash = detector.check_nash_equilibrium(modules)
    print(f"  Nash equilibrium detected: {is_nash}")

    if not is_nash:
        print("  FAILURE: Nash equilibrium was NOT detected after stagnation.")
        print("  Debug info:")
        for module in modules:
            recent = detector.get_recent_history(module, window=5)
            print(f"    {module}: recent history = {recent}")
        sys.exit(1)
    else:
        print("  SUCCESS: Nash equilibrium correctly detected.")

    # Step 5: Verify coordinated mutation plan is generated
    print("\n[Step 5] Verifying coordinated mutation plan generation...")
    try:
        mutation_plan = forcer.generate_coordinated_mutation(modules)
        print(f"  Mutation plan generated: {mutation_plan}")

        if mutation_plan:
            print("  SUCCESS: Coordinated mutation plan is non-empty.")
            print(f"  Plan details:")
            for module, mutations in mutation_plan.items():
                print(f"    {module}: {mutations}")
        else:
            print("  FAILURE: Mutation plan is empty.")
            sys.exit(1)
    except Exception as e:
        print(f"  FAILURE: Exception during mutation plan generation: {e}")
        sys.exit(1)

    # Final summary
    print("\n" + "=" * 60)
    print("INTEGRATION TEST PASSED")
    print("=" * 60)
    print("\nSummary:")
    print("  - 5 improvement cycles simulated")
    print("  - 3 stagnation cycles simulated")
    print("  - Nash equilibrium detected: YES")
    print("  - Coordinated mutation plan generated: YES")
    print("\nAll verifications passed successfully.")


if __name__ == "__main__":
    main()