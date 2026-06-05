import os
import sys
import json
import importlib
import pkgutil
from typing import Dict, List, Tuple, Set

# Add project root to path if needed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Define the components directory (adjust path as needed)
COMPONENTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'components')
TEST_DIR = os.path.join(os.path.dirname(__file__))

def discover_components() -> List[str]:
    """Discover all component modules in the components directory."""
    components = []
    if not os.path.exists(COMPONENTS_DIR):
        print(f"Warning: Components directory not found at {COMPONENTS_DIR}")
        return components
    
    for item in os.listdir(COMPONENTS_DIR):
        item_path = os.path.join(COMPONENTS_DIR, item)
        if os.path.isdir(item_path) and not item.startswith('__'):
            components.append(item)
        elif item.endswith('.py') and not item.startswith('__'):
            components.append(item[:-3])
    
    return sorted(components)

def discover_integration_tests() -> Dict[str, Set[str]]:
    """Discover integration test files and map them to component pairs."""
    test_mapping = {}
    
    if not os.path.exists(TEST_DIR):
        return test_mapping
    
    for root, dirs, files in os.walk(TEST_DIR):
        for file in files:
            if file.startswith('test_integration_') and file.endswith('.py'):
                # Extract component names from filename pattern: test_integration_comp1_comp2.py
                parts = file.replace('test_integration_', '').replace('.py', '').split('_')
                if len(parts) >= 2:
                    comp1 = parts[0]
                    comp2 = '_'.join(parts[1:])
                    pair = (comp1, comp2)
                    test_path = os.path.relpath(os.path.join(root, file), TEST_DIR)
                    if pair not in test_mapping:
                        test_mapping[pair] = set()
                    test_mapping[pair].add(test_path)
    
    return test_mapping

def generate_coverage_matrix(components: List[str], test_mapping: Dict[str, Set[str]]) -> Dict[str, Dict[str, bool]]:
    """Generate a coverage matrix showing which component pairs have integration tests."""
    matrix = {}
    for comp1 in components:
        matrix[comp1] = {}
        for comp2 in components:
            if comp1 == comp2:
                matrix[comp1][comp2] = None  # Self-pair not applicable
            else:
                # Check both orderings
                pair1 = (comp1, comp2)
                pair2 = (comp2, comp1)
                has_test = pair1 in test_mapping or pair2 in test_mapping
                matrix[comp1][comp2] = has_test
    return matrix

def print_coverage_report(matrix: Dict[str, Dict[str, bool]], components: List[str]):
    """Print a human-readable coverage report."""
    print("\n=== Integration Test Coverage Matrix ===\n")
    
    # Print header
    header = f"{'Component':<20}"
    for comp in components:
        header += f"{comp:<15}"
    print(header)
    print("-" * (20 + 15 * len(components)))
    
    # Print rows
    for comp1 in components:
        row = f"{comp1:<20}"
        for comp2 in components:
            if comp1 == comp2:
                row += f"{'N/A':<15}"
            else:
                covered = matrix[comp1][comp2]
                status = "✓" if covered else "✗"
                row += f"{status:<15}"
        print(row)
    
    print("\n✓ = Integration test exists")
    print("✗ = No integration test found")
    print("N/A = Self-pair (not applicable)\n")

def print_summary(matrix: Dict[str, Dict[str, bool]], components: List[str]):
    """Print summary statistics."""
    total_pairs = 0
    covered_pairs = 0
    uncovered_pairs = []
    
    for comp1 in components:
        for comp2 in components:
            if comp1 != comp2:
                total_pairs += 1
                if matrix[comp1][comp2]:
                    covered_pairs += 1
                else:
                    uncovered_pairs.append((comp1, comp2))
    
    coverage_percentage = (covered_pairs / total_pairs * 100) if total_pairs > 0 else 0
    
    print("=== Coverage Summary ===")
    print(f"Total component pairs: {total_pairs}")
    print(f"Covered pairs: {covered_pairs}")
    print(f"Uncovered pairs: {total_pairs - covered_pairs}")
    print(f"Coverage: {coverage_percentage:.1f}%")
    
    if uncovered_pairs:
        print("\nUncovered pairs:")
        for comp1, comp2 in sorted(uncovered_pairs):
            print(f"  - {comp1} <-> {comp2}")

def save_matrix_to_json(matrix: Dict[str, Dict[str, bool]], output_path: str = "coverage_matrix.json"):
    """Save the coverage matrix to a JSON file for use by the feasibility estimator."""
    serializable_matrix = {}
    for comp1 in matrix:
        serializable_matrix[comp1] = {}
        for comp2 in matrix[comp1]:
            serializable_matrix[comp1][comp2] = matrix[comp1][comp2]
    
    with open(output_path, 'w') as f:
        json.dump(serializable_matrix, f, indent=2)
    
    print(f"Coverage matrix saved to {output_path}")

def main():
    """Main function to scan and report integration test coverage."""
    print("Scanning for components and integration tests...")
    
    components = discover_components()
    if not components:
        print("No components found. Check the COMPONENTS_DIR path.")
        return
    
    print(f"Found {len(components)} components: {', '.join(components)}")
    
    test_mapping = discover_integration_tests()
    print(f"Found {len(test_mapping)} integration test pairs")
    
    matrix = generate_coverage_matrix(components, test_mapping)
    
    print_coverage_report(matrix, components)
    print_summary(matrix, components)
    
    # Save for feasibility estimator
    save_matrix_to_json(matrix)
    
    # Return coverage percentage for potential CI integration
    total_pairs = sum(1 for c1 in components for c2 in components if c1 != c2)
    covered_pairs = sum(1 for c1 in components for c2 in components if c1 != c2 and matrix[c1][c2])
    coverage = (covered_pairs / total_pairs * 100) if total_pairs > 0 else 0
    
    return coverage

if __name__ == "__main__":
    coverage = main()
    if coverage is not None:
        print(f"\nFinal coverage: {coverage:.1f}%")
        # Exit with non-zero if coverage is below threshold (optional)
        # if coverage < 50:
        #     sys.exit(1)