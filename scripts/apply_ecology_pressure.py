import os
import sys

# Add the project root to sys.path so that core.ecology_engine can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ecology_engine import EcologyEngine


def main():
    tests_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests")
    if not os.path.isdir(tests_dir):
        print(f"Error: tests directory not found at {tests_dir}")
        sys.exit(1)

    engine = EcologyEngine(tests_dir)
    engine.scan_test_files()

    missing = engine.identify_missing_test_types()
    if not missing:
        print("All test types are present. No new test files needed.")
        return

    print(f"Missing test types: {', '.join(missing)}")
    generated = engine.generate_missing_tests(missing)
    for test_type, filepath in generated.items():
        print(f"Generated {test_type} test: {filepath}")

    print("Ecology pressure applied successfully.")


if __name__ == "__main__":
    main()