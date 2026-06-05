#!/usr/bin/env python3
"""Standalone test runner for Nash Equilibrium detection.

This script imports and runs the Nash equilibrium test directly,
bypassing any test framework dependencies. It can be executed
even in minimal environments where pytest or unittest is not available.
"""

import sys
import os
import json
import importlib.util

# Add the project root to the path so we can import modules directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def import_module_from_path(module_name, file_path):
    """Import a module from a file path without relying on the module system."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        raise ImportError(f"Could not load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_nash_test():
    """Run the Nash equilibrium detection test directly."""
    print("=" * 60)
    print("Nash Equilibrium Detection Test Runner")
    print("=" * 60)

    # Try to import the nash detector module
    nash_detector_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "modules",
        "nash_detector.py"
    )

    if not os.path.exists(nash_detector_path):
        print(f"[ERROR] Nash detector module not found at: {nash_detector_path}")
        return False

    try:
        nash_detector = import_module_from_path("nash_detector", nash_detector_path)
        print("[OK] Successfully imported nash_detector module")
    except ImportError as e:
        print(f"[ERROR] Failed to import nash_detector: {e}")
        return False

    # Check if the NashEquilibriumDetector class exists
    if not hasattr(nash_detector, 'NashEquilibriumDetector'):
        print("[ERROR] NashEquilibriumDetector class not found in module")
        return False

    # Create mock module performance data for testing
    print("\n[INFO] Creating mock module performance data...")
    mock_data = {
        "module_a": {
            "performance": 0.85,
            "complexity": 0.3,
            "dependencies": ["module_b", "module_c"]
        },
        "module_b": {
            "performance": 0.72,
            "complexity": 0.5,
            "dependencies": ["module_c"]
        },
        "module_c": {
            "performance": 0.91,
            "complexity": 0.2,
            "dependencies": []
        },
        "module_d": {
            "performance": 0.65,
            "complexity": 0.7,
            "dependencies": ["module_a", "module_e"]
        },
        "module_e": {
            "performance": 0.78,
            "complexity": 0.4,
            "dependencies": ["module_b"]
        }
    }

    # Initialize the detector
    print("[INFO] Initializing NashEquilibriumDetector...")
    try:
        detector = nash_detector.NashEquilibriumDetector()
        print("[OK] Detector initialized successfully")
    except Exception as e:
        print(f"[ERROR] Failed to initialize detector: {e}")
        return False

    # Run detection
    print("\n[INFO] Running Nash equilibrium detection...")
    try:
        if hasattr(detector, 'detect'):
            result = detector.detect(mock_data)
        elif hasattr(detector, 'find_nash_equilibria'):
            result = detector.find_nash_equilibria(mock_data)
        elif hasattr(detector, 'analyze'):
            result = detector.analyze(mock_data)
        else:
            print("[ERROR] No suitable detection method found on detector object")
            return False

        print("[OK] Detection completed successfully")
    except Exception as e:
        print(f"[ERROR] Detection failed: {e}")
        return False

    # Display results
    print("\n" + "=" * 60)
    print("Detection Results")
    print("=" * 60)

    if isinstance(result, dict):
        print(json.dumps(result, indent=2))
    elif isinstance(result, list):
        for i, item in enumerate(result):
            print(f"  Equilibrium {i+1}: {item}")
    else:
        print(f"  Result: {result}")

    # Validate basic expectations
    print("\n" + "=" * 60)
    print("Validation")
    print("=" * 60)

    all_passed = True

    # Check that result is not None
    if result is None:
        print("[FAIL] Result is None")
        all_passed = False
    else:
        print("[PASS] Result is not None")

    # Check that result contains expected structure
    if isinstance(result, dict):
        if "equilibria" in result or "nash_equilibria" in result:
            print("[PASS] Result contains equilibrium data")
        else:
            print("[WARN] Result does not contain expected 'equilibria' key")
    elif isinstance(result, list):
        if len(result) > 0:
            print(f"[PASS] Found {len(result)} equilibrium candidates")
        else:
            print("[WARN] No equilibrium candidates found")

    print("\n" + "=" * 60)
    if all_passed:
        print("OVERALL: ALL TESTS PASSED")
    else:
        print("OVERALL: SOME TESTS FAILED")
    print("=" * 60)

    return all_passed


def main():
    """Main entry point for the standalone test runner."""
    print("Nash Equilibrium Standalone Test Runner")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print()

    success = run_nash_test()

    print()
    if success:
        print("Test completed successfully.")
        sys.exit(0)
    else:
        print("Test completed with failures.")
        sys.exit(1)


if __name__ == "__main__":
    main()