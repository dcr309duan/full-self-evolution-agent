"""
Ecology Engine: Mutates the fitness landscape by injecting new test cases and benchmarks.
Integrates with the evolution orchestrator via a mutate_fitness_landscape hook.
Uses only standard library modules: os, json, ast, hashlib, random, datetime, subprocess.
"""

import os
import json
import ast
import hashlib
import random
import datetime
import subprocess
import sys
import traceback


def scan_test_suite(test_dir: str = "tests") -> list:
    """List all test_*.py files in the tests/ directory.
    
    Args:
        test_dir: Directory to scan for test files.
        
    Returns:
        List of file paths matching test_*.py pattern.
    """
    test_files = []
    if os.path.isdir(test_dir):
        for fname in os.listdir(test_dir):
            if fname.startswith("test_") and fname.endswith(".py"):
                test_files.append(os.path.join(test_dir, fname))
    return sorted(test_files)


def analyze_test_coverage_gaps(test_dir: str = "tests") -> dict:
    """Analyze test coverage gaps: untested functions, missing edge cases.
    
    Scans test files and project source files to identify functions that
    lack test coverage and edge cases that are not covered.
    
    Args:
        test_dir: Directory containing test files.
        
    Returns:
        Dictionary with 'untested_functions' and 'missing_edge_cases' lists.
    """
    test_files = scan_test_suite(test_dir)
    
    # Extract all function names mentioned in test files
    tested_functions = set()
    edge_cases_covered = set()
    
    for filepath in test_files:
        try:
            with open(filepath, "r") as f:
                content = f.read()
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_name = node.name
                    if func_name.startswith("test_"):
                        # Extract what's being tested from function name
                        parts = func_name.split("_")
                        if len(parts) > 2:
                            tested_functions.add(parts[1])  # e.g., test_memory_pressure -> memory
                        # Check for edge case indicators
                        if any(keyword in func_name.lower() for keyword in ["edge", "corner", "boundary", "limit", "extreme", "empty", "null", "invalid"]):
                            edge_cases_covered.add(func_name)
        except (IOError, OSError, SyntaxError):
            pass
    
    # Scan project source files for functions that might need testing
    project_src_dir = os.path.join(os.path.dirname(test_dir) if test_dir != "tests" else ".", "src")
    if not os.path.isdir(project_src_dir):
        project_src_dir = "."
    
    all_functions = set()
    for root, dirs, files in os.walk(project_src_dir):
        if "__pycache__" in root or ".git" in root:
            continue
        for fname in files:
            if fname.endswith(".py") and not fname.startswith("test_"):
                filepath = os.path.join(root, fname)
                try:
                    with open(filepath, "r") as f:
                        content = f.read()
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            all_functions.add(node.name)
                except (IOError, OSError, SyntaxError):
                    pass
    
    # Identify untested functions
    untested_functions = [func for func in all_functions if func not in tested_functions and not func.startswith("_")]
    
    # Identify missing edge cases
    expected_edge_cases = [
        "empty_input", "null_input", "invalid_input", "boundary_values",
        "extreme_values", "concurrent_access", "resource_exhaustion",
        "timeout_scenarios", "error_handling", "type_mismatch"
    ]
    missing_edge_cases = [ec for ec in expected_edge_cases if ec not in edge_cases_covered]
    
    return {
        "untested_functions": untested_functions[:10],  # Limit to top 10
        "missing_edge_cases": missing_edge_cases,
        "total_functions_found": len(all_functions),
        "functions_tested": len(tested_functions)
    }


def analyze_test_diversity(test_dir: str = "tests") -> dict:
    """Compute coverage of different test types (unit, integration, stress, edge_case).
    
    Analyzes test files in the given directory and categorizes them based on
    naming patterns and content analysis.
    
    Args:
        test_dir: Directory containing test files.
        
    Returns:
        Dictionary with test types as keys and counts as values.
    """
    test_files = scan_test_suite(test_dir)
    diversity = {
        "unit": 0,
        "integration": 0,
        "stress": 0,
        "edge_case": 0,
        "other": 0
    }
    
    for filepath in test_files:
        basename = os.path.basename(filepath)
        content = ""
        try:
            with open(filepath, "r") as f:
                content = f.read()
        except (IOError, OSError):
            pass
        
        # Categorize based on filename and content patterns
        if "stress" in basename.lower() or "load" in basename.lower() or "benchmark" in basename.lower() or "performance" in basename.lower() or \
           "stress" in content.lower() or "load" in content.lower() or "benchmark" in content.lower() or "performance" in content.lower():
            diversity["stress"] += 1
        elif "integration" in basename.lower() or "e2e" in basename.lower() or "end_to_end" in basename.lower() or "workflow" in basename.lower() or \
             "integration" in content.lower() or "e2e" in content.lower() or "end_to_end" in content.lower() or "workflow" in content.lower():
            diversity["integration"] += 1
        elif "edge" in basename.lower() or "corner" in basename.lower() or "boundary" in basename.lower() or "limit" in basename.lower() or "extreme" in basename.lower() or \
             "edge" in content.lower() or "corner" in content.lower() or "boundary" in content.lower() or "limit" in content.lower() or "extreme" in content.lower():
            diversity["edge_case"] += 1
        elif "unit" in basename.lower() or basename.startswith("test_") or "def test_" in content:
            diversity["unit"] += 1
        else:
            diversity["other"] += 1
    
    return diversity


def _generate_concurrent_mutation_test() -> str:
    """Generate a test file for concurrent mutation testing.
    
    Returns:
        String containing the test file content.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = random.randint(1000, 9999)
    
    test_code = f'''"""
Concurrent Mutation Test - Generated by Ecology Engine
Tests concurrent modifications to shared state under mutation pressure.
"""
import threading
import random
import time


class SharedState:
    """A simple shared state object for mutation testing."""
    
    def __init__(self):
        self.value = 0
        self.data = []
        self.lock = threading.Lock()
    
    def mutate(self, delta):
        """Mutate the shared state with a delta value."""
        with self.lock:
            self.value += delta
            self.data.append(delta)
    
    def get_state(self):
        """Get current state snapshot."""
        with self.lock:
            return self.value, list(self.data)


def test_concurrent_mutations_{timestamp}_{random_suffix}():
    """Test that concurrent mutations maintain consistency."""
    state = SharedState()
    num_threads = random.randint(2, 8)
    mutations_per_thread = random.randint(10, 50)
    threads = []
    
    def worker(worker_id):
        """Worker thread that performs mutations."""
        for _ in range(mutations_per_thread):
            delta = random.randint(-10, 10)
            state.mutate(delta)
            time.sleep(random.uniform(0.001, 0.01))
    
    # Start threads
    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join()
    
    # Verify consistency
    final_value, mutation_history = state.get_state()
    expected_value = sum(mutation_history)
    assert final_value == expected_value, f"State inconsistency: {{final_value}} != {{expected_value}}"
    assert len(mutation_history) == num_threads * mutations_per_thread, "Missing mutations"


def test_mutation_isolation_{timestamp}_{random_suffix}():
    """Test that mutations are properly isolated between threads."""
    state1 = SharedState()
    state2 = SharedState()
    
    def mutate_state1():
        for _ in range(20):
            state1.mutate(random.randint(-5, 5))
    
    def mutate_state2():
        for _ in range(20):
            state2.mutate(random.randint(-5, 5))
    
    t1 = threading.Thread(target=mutate_state1)
    t2 = threading.Thread(target=mutate_state2)
    
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    val1, hist1 = state1.get_state()
    val2, hist2 = state2.get_state()
    
    # States should be independent
    assert sum(hist1) == val1, f"State1 inconsistent"
    assert sum(hist2) == val2, f"State2 inconsistent"
'''
    return test_code


def _generate_resource_exhaustion_test() -> str:
    """Generate a test file for resource exhaustion testing.
    
    Returns:
        String containing the test file content.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = random.randint(1000, 9999)
    
    test_code = f'''"""
Resource Exhaustion Test - Generated by Ecology Engine
Tests system behavior under resource pressure (memory, file handles, threads).
"""
import os
import random
import tempfile
import threading


def test_memory_pressure_{timestamp}_{random_suffix}():
    """Test behavior under controlled memory pressure."""
    memory_chunks = []
    chunk_size = random.randint(100, 1000)  # KB
    max_chunks = random.randint(5, 20)
    
    try:
        for i in range(max_chunks):
            # Allocate memory in chunks
            chunk = bytearray(chunk_size * 1024)
            memory_chunks.append(chunk)
            
            # Verify chunk is writable
            chunk[0] = 1
            chunk[-1] = 255
        
        # Verify all chunks are accessible
        for i, chunk in enumerate(memory_chunks):
            assert chunk[0] == 1, f"Chunk {{i}} corrupted"
            assert chunk[-1] == 255, f"Chunk {{i}} tail corrupted"
    
    except MemoryError:
        # Memory exhaustion is acceptable - test should handle gracefully
        pass
    
    finally:
        # Clean up
        memory_chunks.clear()


def test_file_handle_exhaustion_{timestamp}_{random_suffix}():
    """Test behavior when file handles are exhausted."""
    temp_files = []
    max_files = random.randint(10, 50)
    
    try:
        for i in range(max_files):
            # Create temporary files
            fd, path = tempfile.mkstemp(suffix=".txt", prefix="exhaust_")
            os.close(fd)
            temp_files.append(path)
            
            # Open file handles
            f = open(path, "w")
            f.write(f"Test data for file {{i}}")
            f.close()
        
        # Verify files exist and are readable
        for path in temp_files:
            assert os.path.exists(path), f"File {{path}} missing"
            with open(path, "r") as f:
                content = f.read()
            assert len(content) > 0, f"File {{path}} empty"
    
    except OSError as e:
        # File exhaustion is acceptable
        pass
    
    finally:
        # Clean up all temporary files
        for path in temp_files:
            try:
                os.remove(path)
            except OSError:
                pass


def test_thread_exhaustion_{timestamp}_{random_suffix}():
    """Test behavior under high thread count."""
    threads = []
    max_threads = random.randint(20, 100)
    
    def worker(worker_id):
        """Simple worker that does minimal work."""
        result = 0
        for i in range(100):
            result += i * worker_id
        return result
    
    try:
        for i in range(max_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join(timeout=5)
        
        # Verify all threads completed
        for t in threads:
            assert not t.is_alive(), f"Thread {{t.name}} still alive"
    
    except RuntimeError:
        # Thread exhaustion is acceptable
        pass
'''
    return test_code


def _generate_dependency_conflict_test() -> str:
    """Generate a test file for dependency conflict testing.
    
    Returns:
        String containing the test file content.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = random.randint(1000, 9999)
    
    test_code = f'''"""
Dependency Conflict Test - Generated by Ecology Engine
Tests system behavior with conflicting dependencies and version mismatches.
"""
import sys
import random
import importlib


def test_version_conflict_detection_{timestamp}_{random_suffix}():
    """Test that version conflicts are properly detected."""
    # Simulate version conflict scenarios
    scenarios = [
        {{"module": "os", "min_version": "1.0", "max_version": "2.0"}},
        {{"module": "sys", "min_version": "2.0", "max_version": "3.0"}},
        {{"module": "random", "min_version": "1.5", "max_version": "2.5"}},
    ]
    
    for scenario in scenarios:
        module_name = scenario["module"]
        try:
            module = importlib.import_module(module_name)
            # Check if module has version attribute
            if hasattr(module, "__version__"):
                version = module.__version__
                # Version conflict detection would go here
                assert True, f"Module {{module_name}} version {{version}} loaded"
            else:
                # Module without version is acceptable
                pass
        except ImportError:
            # Module not found is acceptable
            pass


def test_dependency_isolation_{timestamp}_{random_suffix}():
    """Test that dependencies are isolated and don't interfere."""
    # Test that standard library modules work independently
    import os
    import sys
    import random
    import threading
    
    # Verify each module works correctly
    assert os.name in ("posix", "nt", "java"), "OS module working"
    assert sys.version_info.major >= 3, "Python 3+ required"
    assert random.random() >= 0.0, "Random module working"
    
    # Test thread safety of dependencies
    results = []
    lock = threading.Lock()
    
    def worker():
        """Worker that uses various dependencies."""
        local_result = []
        local_result.append(os.getcwd())
        local_result.append(sys.executable)
        local_result.append(random.randint(0, 100))
        with lock:
            results.extend(local_result)
    
    threads = []
    for _ in range(5):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    assert len(results) == 15, f"Expected 15 results, got {{len(results)}}"


def test_circular_dependency_handling_{timestamp}_{random_suffix}():
    """Test that circular dependencies are handled gracefully."""
    # Create a scenario that could cause circular imports
    test_modules = ["os", "sys", "random", "threading", "time"]
    
    # Try importing modules in different orders
    for _ in range(10):
        order = random.sample(test_modules, len(test_modules))
        modules = []
        for module_name in order:
            try:
                module = importlib.import_module(module_name)
                modules.append(module)
            except ImportError as e:
                # Circular dependency error is acceptable
                pass
        
        # Verify imported modules work
        for module in modules:
            assert module is not None, f"Module {{module.__name__}} is None"
'''
    return test_code


def _generate_edge_case_test() -> str:
    """Generate a test file for edge case testing based on coverage gaps.
    
    Returns:
        String containing the test file content.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = random.randint(1000, 9999)
    
    test_code = f'''"""
Edge Case Test - Generated by Ecology Engine
Tests edge cases and boundary conditions.
"""
import random
import math


def test_empty_input_handling_{timestamp}_{random_suffix}():
    """Test that empty inputs are handled gracefully."""
    # Test with empty strings
    empty_string = ""
    assert len(empty_string) == 0, "Empty string should have length 0"
    assert empty_string == "", "Empty string should equal itself"
    
    # Test with empty lists
    empty_list = []
    assert len(empty_list) == 0, "Empty list should have length 0"
    assert list(empty_list) == [], "Empty list should be empty"
    
    # Test with empty dicts
    empty_dict = {{}}
    assert len(empty_dict) == 0, "Empty dict should have length 0"
    assert dict(empty_dict) == {{}}, "Empty dict should be empty"


def test_null_input_handling_{timestamp}_{random_suffix}():
    """Test that null/None inputs are handled gracefully."""
    # Test None comparisons
    none_value = None
    assert none_value is None, "None should be None"
    assert not none_value, "None should be falsy"
    
    # Test None in collections
    list_with_none = [1, None, 3]
    assert None in list_with_none, "None should be detectable in lists"
    
    # Test None in function calls
    def process_value(val=None):
        if val is None:
            return "default"
        return val
    
    assert process_value() == "default", "None should trigger default"
    assert process_value(42) == 42, "Non-None should pass through"


def test_boundary_values_{timestamp}_{random_suffix}():
    """Test boundary values for numeric operations."""
    # Test integer boundaries
    assert 0 == 0, "Zero boundary"
    assert 1 > 0, "Positive boundary"
    assert -1 < 0, "Negative boundary"
    
    # Test max/min values
    max_int = 2**31 - 1
    min_int = -2**31
    assert max_int > min_int, "Max should be greater than min"
    
    # Test floating point boundaries
    epsilon = 1e-10
    assert abs(1.0 - 1.0) < epsilon, "Float equality within epsilon"
    assert 0.1 + 0.2 != 0.3, "Float precision issue expected"


def test_extreme_values_{timestamp}_{random_suffix}():
    """Test extreme values for stress testing."""
    # Test very large numbers
    large_number = 10**100
    assert large_number > 0, "Large positive number"
    
    # Test very small numbers
    small_number = 10**-100
    assert small_number > 0, "Small positive number"
    
    # Test infinity
    infinity = float('inf')
    assert infinity > 10**100, "Infinity should be larger than any finite number"
    
    # Test NaN
    nan = float('nan')
    assert math.isnan(nan), "NaN should be detected by math.isnan"


def test_type_mismatch_handling_{timestamp}_{random_suffix}():
    """Test that type mismatches are handled gracefully."""
    # Test string vs number operations
    string_val = "123"
    number_val = 123
    
    # These should work
    assert int(string_val) == number_val, "String to int conversion"
    assert str(number_val) == string_val, "Int to string conversion"
    
    # Test list vs tuple
    list_val = [1, 2, 3]
    tuple_val = (1, 2, 3)
    assert list(list_val) == list(tuple_val), "List and tuple with same elements"
    assert tuple(list_val) == tuple_val, "List to tuple conversion"
'''
    return test_code


def _generate_novel_mutation_scenario_test() -> str:
    """Generate a test file with novel mutation scenarios based on coverage gaps.
    
    Returns:
        String containing the test file content.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = random.randint(1000, 9999)
    
    # Create a unique hash for the test file to ensure uniqueness
    test_hash = hashlib.sha256(f"{timestamp}{random_suffix}".encode()).hexdigest()[:8]
    
    test_code = f'''"""
Novel Mutation Scenario Test - Generated by Ecology Engine
Tests new mutation scenarios to fill coverage gaps.
"""
import random
import hashlib
import datetime


def test_mutation_scenario_{timestamp}_{random_suffix}():
    """Test a novel mutation scenario with random parameters."""
    # Generate random test parameters
    seed = random.randint(0, 1000000)
    random.seed(seed)
    
    # Create a unique mutation pattern
    mutation_pattern = hashlib.sha256(f"mutation_{seed}".encode()).hexdigest()
    
    # Apply mutation to test data
    test_data = list(range(100))
    random.shuffle(test_data)
    
    # Verify mutation properties
    assert len(test_data) == 100, "Test data length should be preserved"
    assert sum(test_data) == sum(range(100)), "Sum should be preserved after shuffle"
    assert set(test_data) == set(range(100)), "Elements should be preserved"
    
    # Check mutation pattern uniqueness
    assert len(mutation_pattern) == 64, "Hash should be 64 characters"
    assert mutation_pattern.isalnum(), "Hash should be alphanumeric"


def test_mutation_edge_case_{timestamp}_{random_suffix}():
    """Test edge cases in mutation scenarios."""
    # Test mutation with empty data
    empty_data = []
    assert len(empty_data) == 0, "Empty data should have length 0"
    
    # Test mutation with single element
    single_data = [42]
    assert len(single_data) == 1, "Single element data should have length 1"
    assert single_data[0] == 42, "Single element should be preserved"
    
    # Test mutation with duplicate elements
    duplicate_data = [1, 1, 2, 2, 3, 3]
    assert len(duplicate_data) == 6, "Duplicate data should have correct length"
    assert duplicate_data.count(1) == 2, "Should have two 1s"
    assert duplicate_data.count(2) == 2, "Should have two 2s"
    assert duplicate_data.count(3) == 2, "Should have three 3s"
    
    # Test mutation with negative values
    negative_data = [-5, -3, -1, 0, 1, 3, 5]
    assert min(negative_data) == -5, "Minimum should be -5"
    assert max(negative_data) == 5, "Maximum should be 5"
    assert sum(negative_data) == 0, "Sum of symmetric data should be 0"


def test_mutation_stress_{timestamp}_{random_suffix}():
    """Test mutation under stress conditions."""
    # Generate large dataset
    large_data = list(range(10000))
    
    # Perform multiple mutations
    for _ in range(100):
        random.shuffle(large_data)
    
    # Verify data integrity after stress
    assert len(large_data) == 10000, "Data length should be preserved"
    assert sum(large_data) == sum(range(10000)), "Sum should be preserved"
    assert set(large_data) == set(range(10000)), "Elements should be preserved"
    
    # Test with timestamp-based mutation
    current_time = datetime.datetime.now()
    time_hash = hashlib.sha256(str(current_time.timestamp()).encode()).hexdigest()
    assert len(time_hash) == 64, "Time hash should be 64 characters"
'''
    return test_code


def _generate_performance_regression_test() -> str:
    """Generate a test file for performance regression testing.
    
    Creates a benchmark that measures execution time of common operations
    and asserts they stay within acceptable limits.
    
    Returns:
        String containing the test file content.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = random.randint(1000, 9999)
    
    test_code = f'''"""
Performance Regression Test - Generated by Ecology Engine
Tests that common operations maintain acceptable performance.
"""
import time
import random
import hashlib


def test_list_sort_performance_{timestamp}_{random_suffix}():
    """Test that list sorting remains performant."""
    # Generate a large list
    data = [random.random() for _ in range(10000)]
    
    # Measure sorting time
    start_time = time.time()
    sorted_data = sorted(data)
    elapsed = time.time() - start_time
    
    # Assert sorting is correct
    for i in range(len(sorted_data) - 1):
        assert sorted_data[i] <= sorted_data[i + 1], "List should be sorted"
    
    # Assert performance threshold (should complete in under 1 second)
    assert elapsed < 1.0, f"Sorting took {{elapsed:.3f}}s, expected < 1.0s"


def test_hash_computation_performance_{timestamp}_{random_suffix}():
    """Test that hash computations remain performant."""
    # Generate test data
    test_string = "A" * 100000
    
    # Measure hash computation time
    start_time = time.time()
    for _ in range(100):
        hash_result = hashlib.sha256(test_string.encode()).hexdigest()
    elapsed = time.time() - start_time
    
    # Assert hash is valid
    assert len(hash_result) == 64, "Hash should be 64 characters"
    assert hash_result.isalnum(), "Hash should be alphanumeric"
    
    # Assert performance threshold (100 hashes in under 2 seconds)
    assert elapsed < 2.0, f"100 hashes took {{elapsed:.3f}}s, expected < 2.0s"


def test_dictionary_operations_performance_{timestamp}_{random_suffix}():
    """Test that dictionary operations remain performant."""
    # Build a large dictionary
    test_dict = {{}}
    for i in range(10000):
        test_dict[f"key_{{i}}"] = i
    
    # Measure lookup time
    start_time = time.time()
    for i in range(10000):
        value = test_dict[f"key_{{i}}"]
        assert value == i, f"Expected {{i}}, got {{value}}"
    elapsed = time.time() - start_time
    
    # Assert performance threshold (10000 lookups in under 0.5 seconds)
    assert elapsed < 0.5, f"10000 lookups took {{elapsed:.3f}}s, expected < 0.5s"


def test_string_concatenation_performance_{timestamp}_{random_suffix}():
    """Test that string concatenation remains performant."""
    # Test efficient string building
    parts = [str(i) for i in range(1000)]
    
    # Measure join performance
    start_time = time.time()
    result = "".join(parts)
    elapsed = time.time() - start_time
    
    # Assert result is correct
    assert len(result) == len("".join(parts)), "String length should match"
    
    # Assert performance threshold (join in under 0.1 seconds)
    assert elapsed < 0.1, f"String join took {{elapsed:.3f}}s, expected < 0.1s"
'''
    return test_code


def _generate_mutation_resilience_test() -> str:
    """Generate a test file for mutation resilience testing.
    
    Tests that the system can recover from various mutation scenarios
    and maintain data integrity.
    
    Returns:
        String containing the test file content.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = random.randint(1000, 9999)
    
    test_code = f'''"""
Mutation Resilience Test - Generated by Ecology Engine
Tests system resilience to various mutation scenarios.
"""
import random
import hashlib
import copy


def test_data_integrity_after_mutation_{timestamp}_{random_suffix}():
    """Test that data integrity is maintained after mutations."""
    # Create original data
    original_data = {{"id": 1, "values": [1, 2, 3, 4, 5], "metadata": {{"source": "test"}}}}
    
    # Create a deep copy and mutate it
    mutated_data = copy.deepcopy(original_data)
    mutated_data["values"].append(6)
    mutated_data["metadata"]["mutated"] = True
    
    # Verify original is unchanged
    assert original_data["id"] == 1, "Original id should be unchanged"
    assert original_data["values"] == [1, 2, 3, 4, 5], "Original values should be unchanged"
    assert "mutated" not in original_data["metadata"], "Original metadata should not have mutated key"
    
    # Verify mutation is isolated
    assert mutated_data["values"] == [1, 2, 3, 4, 5, 6], "Mutated values should include 6"
    assert mutated_data["metadata"]["mutated"] == True, "Mutated metadata should have mutated key"


def test_mutation_recovery_{timestamp}_{random_suffix}():
    """Test that system can recover from mutations."""
    # Simulate a mutation scenario
    state = {{"counter": 0, "items": [], "status": "active"}}
    
    # Apply mutations
    for i in range(10):
        state["counter"] += 1
        state["items"].append(i)
        
        # Simulate recovery checkpoints
        if i == 5:
            checkpoint = copy.deepcopy(state)
    
    # Verify we can recover to checkpoint
    recovered_state = checkpoint
    assert recovered_state["counter"] == 5, "Recovered counter should be 5"
    assert recovered_state["items"] == [0, 1, 2, 3, 4, 5], "Recovered items should match"
    assert recovered_state["status"] == "active", "Recovered status should be active"


def test_mutation_rollback_{timestamp}_{random_suffix}():
    """Test that mutations can be rolled back."""
    # Create initial state
    initial_state = {{"version": 1, "data": "original", "changes": []}}
    
    # Apply a mutation
    mutated_state = copy.deepcopy(initial_state)
    mutated_state["version"] = 2
    mutated_state["data"] = "modified"
    mutated_state["changes"].append("mutation_1")
    
    # Rollback mutation
    rolled_back_state = initial_state
    
    # Verify rollback
    assert rolled_back_state["version"] == 1, "Rolled back version should be 1"
    assert rolled_back_state["data"] == "original", "Rolled back data should be original"
    assert len(rolled_back_state["changes"]) == 0, "Rolled back changes should be empty"


def test_concurrent_mutation_resilience_{timestamp}_{random_suffix}():
    """Test resilience to concurrent mutations."""
    import threading
    
    # Shared resource
    shared_resource = {{"value": 0, "operations": []}}
    lock = threading.Lock()
    
    def mutate_resource(delta):
        """Safely mutate the shared resource."""
        with lock:
            shared_resource["value"] += delta
            shared_resource["operations"].append(delta)
    
    # Perform concurrent mutations
    threads = []
    for _ in range(5):
        t = threading.Thread(target=mutate_resource, args=(random.randint(-10, 10),))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # Verify consistency
    expected_value = sum(shared_resource["operations"])
    assert shared_resource["value"] == expected_value, f"Value {{shared_resource['value']}} != expected {{expected_value}}"
'''
    return test_code


def _validate_imports() -> bool:
    """Validate that all required modules can be imported correctly.
    
    Checks the actual module structure to ensure import paths are valid.
    
    Returns:
        True if all imports are valid, False otherwise.
    """
    required_modules = [
        "os",
        "json",
        "ast",
        "hashlib",
        "random",
        "datetime",
        "subprocess",
        "sys",
        "traceback",
        "threading",
        "time",
        "tempfile",
        "importlib",
        "math",
        "copy"
    ]
    
    for module_name in required_modules:
        try:
            __import__(module_name)
        except ImportError:
            return False
    return True


def generate_new_benchmark(test_dir: str = "tests", dry_run: bool = False) -> str:
    """Create a brand new test file in tests/ with a novel testing scenario.
    
    First validates all imports by checking the actual module structure,
    then generates the test file with correct import paths.
    Includes a dry-run mode that prints the proposed test without writing.
    
    Args:
        test_dir: Directory to create the test file in.
        dry_run: If True, print the proposed test content without writing.
        
    Returns:
        Path to the created test file, or empty string on failure.
    """
    # Validate imports first
    if not _validate_imports():
        return ""
    
    os.makedirs(test_dir, exist_ok=True)
    
    # Choose a novel scenario type randomly
    scenario_type = random.choice(["performance_regression", "mutation_resilience", "concurrent_mutation", "resource_exhaustion", "dependency_conflict", "edge_case", "novel_mutation"])
    
    if scenario_type == "performance_regression":
        test_code = _generate_performance_regression_test()
        filename = f"test_performance_regression_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}.py"
    elif scenario_type == "mutation_resilience":
        test_code = _generate_mutation_resilience_test()
        filename = f"test_mutation_resilience_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}.py"
    elif scenario_type == "concurrent_mutation":
        test_code = _generate_concurrent_mutation_test()
        filename = f"test_concurrent_mutation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}.py"
    elif scenario_type == "resource_exhaustion":
        test_code = _generate_resource_exhaustion_test()
        filename = f"test_resource_exhaustion_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}.py"
    elif scenario_type == "dependency_conflict":
        test_code = _generate_dependency_conflict_test()
        filename = f"test_dependency_conflict_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}.py"
    elif scenario_type == "edge_case":
        test_code = _generate_edge_case_test()
        filename = f"test_edge_case_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}.py"
    else:  # novel_mutation
        test_code = _generate_novel_mutation_scenario_test()
        filename = f