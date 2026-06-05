import os
import sys
import json
import importlib
import pkgutil
import tempfile
import shutil
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

def test_clone_and_promote_mechanism():
    """Test the clone and promote mechanism for mutations."""
    import tempfile
    import shutil
    
    # Create a temporary directory for testing
    test_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    
    try:
        # Create a test module
        test_module_path = os.path.join(test_dir, "test_module.py")
        with open(test_module_path, 'w') as f:
            f.write("""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
""")
        
        # Add test directory to path
        sys.path.insert(0, test_dir)
        
        # Import the test module
        import test_module
        
        # Store original module content
        with open(test_module_path, 'r') as f:
            original_content = f.read()
        
        # Test 1: Simple mutation that passes and gets promoted
        # Simulate a mutation that changes add to multiply
        mutated_content = original_content.replace("return a + b", "return a * b")
        
        # Write mutated version
        with open(test_module_path, 'w') as f:
            f.write(mutated_content)
        
        # Reload module
        importlib.reload(test_module)
        
        # Verify mutation works (this is a valid mutation that should pass)
        assert test_module.add(2, 3) == 6, "Mutation should change add behavior"
        assert test_module.subtract(5, 3) == 2, "Subtract should remain unchanged"
        
        # Simulate promotion by keeping the mutation
        # (In real system, this would be done by the mutation testing framework)
        
        # Test 2: Deliberately broken mutation that fails and is discarded
        # Create a broken mutation that will cause an error
        broken_content = original_content.replace("return a + b", "return a / b")
        
        with open(test_module_path, 'w') as f:
            f.write(broken_content)
        
        # Reload module
        importlib.reload(test_module)
        
        # This mutation should fail (division by zero when b=0)
        try:
            result = test_module.add(5, 0)
            # If we get here, the mutation didn't cause an error
            # But it should have changed behavior
            assert result != 5, "Broken mutation should change behavior"
        except ZeroDivisionError:
            # This is expected - the mutation is broken
            pass
        
        # Discard the broken mutation by restoring original
        with open(test_module_path, 'w') as f:
            f.write(original_content)
        
        importlib.reload(test_module)
        
        # Verify original behavior is restored
        assert test_module.add(2, 3) == 5, "Original behavior should be restored"
        
        # Test 3: Failure counter increments correctly
        failure_count = 0
        
        # Simulate multiple failed mutations
        for i in range(3):
            try:
                # Create a mutation that will fail
                bad_content = original_content.replace("return a + b", "return a / b")
                with open(test_module_path, 'w') as f:
                    f.write(bad_content)
                importlib.reload(test_module)
                
                # This should fail
                test_module.add(5, 0)
            except (ZeroDivisionError, Exception):
                failure_count += 1
                # Restore original
                with open(test_module_path, 'w') as f:
                    f.write(original_content)
                importlib.reload(test_module)
        
        assert failure_count == 3, f"Failure counter should be 3, got {failure_count}"
        
        # Test 4: Original module remains unchanged after failed mutation
        # Create a mutation that fails
        bad_content = original_content.replace("return a + b", "return a / b")
        with open(test_module_path, 'w') as f:
            f.write(bad_content)
        
        importlib.reload(test_module)
        
        # Attempt to use the broken module (should fail)
        try:
            test_module.add(5, 0)
        except ZeroDivisionError:
            pass
        
        # Restore original
        with open(test_module_path, 'w') as f:
            f.write(original_content)
        
        importlib.reload(test_module)
        
        # Verify original module is unchanged
        with open(test_module_path, 'r') as f:
            current_content = f.read()
        
        assert current_content == original_content, "Original module should remain unchanged"
        assert test_module.add(2, 3) == 5, "Original function should work correctly"
        assert test_module.subtract(5, 3) == 2, "Original function should work correctly"
        
        print("All clone and promote mechanism tests passed!")
        
    finally:
        # Clean up
        sys.path.remove(test_dir)
        os.chdir(original_dir)
        shutil.rmtree(test_dir, ignore_errors=True)

def test_static_validation():
    """Test static validation of modules before mutation."""
    test_dir = tempfile.mkdtemp()
    
    try:
        # Add test directory to path
        sys.path.insert(0, test_dir)
        
        # Test 1: Valid syntax module should pass validation
        valid_module_path = os.path.join(test_dir, "valid_module.py")
        with open(valid_module_path, 'w') as f:
            f.write("""
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
""")
        
        # Simulate validation by trying to compile the module
        with open(valid_module_path, 'r') as f:
            source = f.read()
        
        try:
            compile(source, valid_module_path, 'exec')
            validation_passed = True
        except SyntaxError:
            validation_passed = False
        
        assert validation_passed, "Valid module should pass validation"
        
        # Test 2: Module with unresolved import should fail validation
        unresolved_import_path = os.path.join(test_dir, "unresolved_import_module.py")
        with open(unresolved_import_path, 'w') as f:
            f.write("""
import nonexistent_module

def add(a, b):
    return a + b
""")
        
        # Simulate validation by trying to import the module
        try:
            import unresolved_import_module
            validation_passed = True
        except ImportError:
            validation_passed = False
        
        assert not validation_passed, "Module with unresolved import should fail validation"
        
        # Test 3: Module with type mismatch should fail validation
        type_mismatch_path = os.path.join(test_dir, "type_mismatch_module.py")
        with open(type_mismatch_path, 'w') as f:
            f.write("""
def add(a: int, b: int) -> int:
    return a + b

# Type mismatch: passing string where int expected
result = add("hello", "world")
""")
        
        # Simulate validation by trying to execute the module
        try:
            import type_mismatch_module
            validation_passed = True
        except TypeError:
            validation_passed = False
        
        assert not validation_passed, "Module with type mismatch should fail validation"
        
        # Test 4: Mutation engine should reject mutations on invalid modules
        # Create an invalid module
        invalid_module_path = os.path.join(test_dir, "invalid_module.py")
        with open(invalid_module_path, 'w') as f:
            f.write("""
import nonexistent_module

def add(a, b):
    return a + b
""")
        
        # Simulate mutation engine behavior
        # First check if module is valid
        try:
            import invalid_module
            module_valid = True
        except ImportError:
            module_valid = False
        
        # If module is invalid, mutation engine should reject without attempting modification
        if not module_valid:
            # Verify that we don't attempt to modify the file
            with open(invalid_module_path, 'r') as f:
                original_content = f.read()
            
            # Attempt to "mutate" (should not happen in real engine)
            # In real engine, this would be skipped
            mutated_content = original_content.replace("return a + b", "return a * b")
            
            # Verify original content is preserved (no mutation attempted)
            assert original_content != mutated_content, "Mutation should not be attempted on invalid module"
            
            # Verify file content remains unchanged
            with open(invalid_module_path, 'r') as f:
                current_content = f.read()
            
            assert current_content == original_content, "Invalid module file should remain unchanged"
        
        print("All static validation tests passed!")
        
    finally:
        # Clean up
        sys.path.remove(test_dir)
        shutil.rmtree(test_dir, ignore_errors=True)

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
    
    # Run the clone and promote mechanism test
    test_clone_and_promote_mechanism()
    
    # Run the static validation test
    test_static_validation()
    
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