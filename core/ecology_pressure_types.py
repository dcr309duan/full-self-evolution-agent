from enum import Enum
from typing import Dict, List, Optional, Any
import json


class PressureType(Enum):
    """Enumeration of all ecology pressure types that can be applied to test suites."""
    PERFORMANCE = "PERFORMANCE"
    COMPLEXITY = "COMPLEXITY"
    EDGE_CASE = "EDGE_CASE"
    RESOURCE_USAGE = "RESOURCE_USAGE"
    CONCURRENCY = "CONCURRENCY"

    @classmethod
    def list_types(cls) -> List[str]:
        """Return list of all pressure type names."""
        return [member.value for member in cls]

    @classmethod
    def from_string(cls, name: str) -> "PressureType":
        """Convert a string to a PressureType, case-insensitive."""
        for member in cls:
            if member.value == name.upper():
                return member
        raise ValueError(f"Unknown pressure type: {name}. Valid types: {cls.list_types()}")


# Mapping of pressure types to their human-readable descriptions
PRESSURE_DESCRIPTIONS: Dict[PressureType, str] = {
    PressureType.PERFORMANCE: "Tests that push the system to its performance limits, measuring execution time and throughput.",
    PressureType.COMPLEXITY: "Tests that introduce high algorithmic complexity to stress logical reasoning and branching.",
    PressureType.EDGE_CASE: "Tests that explore boundary conditions, unusual inputs, and error-prone scenarios.",
    PressureType.RESOURCE_USAGE: "Tests that simulate memory, disk, or network constraints to verify graceful degradation.",
    PressureType.CONCURRENCY: "Tests that introduce parallel execution, race conditions, and synchronization challenges.",
}


# Template generators for each pressure type
def _performance_template(name: str) -> Dict[str, Any]:
    """Generate a performance pressure test template."""
    return {
        "test_name": f"test_performance_{name}",
        "pressure_type": "PERFORMANCE",
        "description": f"Performance stress test for {name}",
        "template_code": f"""
import time

def test_performance_{name}():
    \"\"\"Performance test: measure execution time under load.\"\"\"
    start_time = time.perf_counter()
    # TODO: Implement performance-critical operations for {name}
    # Example: run the target function N times and assert time < threshold
    for _ in range(100):
        pass  # Replace with actual function call
    elapsed = time.perf_counter() - start_time
    assert elapsed < 5.0, f"Performance threshold exceeded: {{elapsed:.2f}}s"
""",
        "metadata": {
            "iterations": 100,
            "max_time_seconds": 5.0,
            "category": "performance"
        }
    }


def _complexity_template(name: str) -> Dict[str, Any]:
    """Generate a complexity pressure test template."""
    return {
        "test_name": f"test_complexity_{name}",
        "pressure_type": "COMPLEXITY",
        "description": f"Complexity stress test for {name}",
        "template_code": f"""
def test_complexity_{name}():
    \"\"\"Complexity test: verify handling of high-complexity inputs.\"\"\"
    # TODO: Generate complex input data for {name}
    # Example: deeply nested structures, large branching factors
    complex_input = None  # Replace with actual complex input
    # result = target_function(complex_input)
    # assert result is not None
    assert True  # Placeholder assertion
""",
        "metadata": {
            "input_complexity": "high",
            "nesting_depth": 10,
            "branching_factor": 5,
            "category": "complexity"
        }
    }


def _edge_case_template(name: str) -> Dict[str, Any]:
    """Generate an edge case pressure test template."""
    return {
        "test_name": f"test_edge_case_{name}",
        "pressure_type": "EDGE_CASE",
        "description": f"Edge case stress test for {name}",
        "template_code": f"""
def test_edge_case_{name}():
    \"\"\"Edge case test: verify behavior at boundaries.\"\"\"
    # TODO: Test boundary conditions for {name}
    # Examples: empty inputs, max values, None, special characters
    edge_inputs = [
        None,
        "",
        [],
        0,
        float('inf'),
        float('-inf'),
        float('nan'),
    ]
    for inp in edge_inputs:
        try:
            # result = target_function(inp)
            pass  # Replace with actual function call
        except Exception as e:
            # Edge cases may raise exceptions; verify they are handled gracefully
            pass
    assert True  # Placeholder assertion
""",
        "metadata": {
            "boundary_values": ["None", "empty", "zero", "infinity", "NaN"],
            "expected_exceptions": True,
            "category": "edge_case"
        }
    }


def _resource_usage_template(name: str) -> Dict[str, Any]:
    """Generate a resource usage pressure test template."""
    return {
        "test_name": f"test_resource_usage_{name}",
        "pressure_type": "RESOURCE_USAGE",
        "description": f"Resource usage stress test for {name}",
        "template_code": f"""
import sys

def test_resource_usage_{name}():
    \"\"\"Resource usage test: verify memory and resource constraints.\"\"\"
    # TODO: Monitor resource consumption for {name}
    # Example: allocate large data structures and check memory limits
    initial_memory = sys.getsizeof([])
    large_data = [0] * 1000000  # 1 million elements
    allocated_memory = sys.getsizeof(large_data)
    # assert allocated_memory < 100 * 1024 * 1024  # Less than 100 MB
    del large_data
    assert True  # Placeholder assertion
""",
        "metadata": {
            "memory_limit_mb": 100,
            "data_size": 1000000,
            "category": "resource_usage"
        }
    }


def _concurrency_template(name: str) -> Dict[str, Any]:
    """Generate a concurrency pressure test template."""
    return {
        "test_name": f"test_concurrency_{name}",
        "pressure_type": "CONCURRENCY",
        "description": f"Concurrency stress test for {name}",
        "template_code": f"""
import threading
import time

def test_concurrency_{name}():
    \"\"\"Concurrency test: verify thread safety and race condition handling.\"\"\"
    results = []
    errors = []
    lock = threading.Lock()

    def worker(thread_id):
        \"\"\"Simulate concurrent access to {name}.\"\"\"
        try:
            # TODO: Call the target function with thread_id
            # result = target_function(thread_id)
            with lock:
                results.append(thread_id)
        except Exception as e:
            with lock:
                errors.append(str(e))

    threads = []
    for i in range(10):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=5)

    assert len(errors) == 0, f"Concurrency errors occurred: {{errors}}"
    assert len(results) == 10, f"Expected 10 results, got {{len(results)}}"
""",
        "metadata": {
            "num_threads": 10,
            "timeout_seconds": 5,
            "category": "concurrency"
        }
    }


# Registry mapping pressure types to their template generators
PRESSURE_TEMPLATE_GENERATORS = {
    PressureType.PERFORMANCE: _performance_template,
    PressureType.COMPLEXITY: _complexity_template,
    PressureType.EDGE_CASE: _edge_case_template,
    PressureType.RESOURCE_USAGE: _resource_usage_template,
    PressureType.CONCURRENCY: _concurrency_template,
}


def generate_pressure_test_template(pressure_type: PressureType, name: str) -> Dict[str, Any]:
    """
    Generate a test template for the given pressure type and name.

    Args:
        pressure_type: The type of pressure to generate a template for.
        name: A descriptive name for the test (e.g., function or module name).

    Returns:
        A dictionary containing the test template with keys:
            - test_name: str
            - pressure_type: str
            - description: str
            - template_code: str
            - metadata: dict

    Raises:
        ValueError: If the pressure type is unknown.
    """
    generator = PRESSURE_TEMPLATE_GENERATORS.get(pressure_type)
    if generator is None:
        raise ValueError(f"No template generator for pressure type: {pressure_type}")
    return generator(name)


def generate_all_templates(name: str) -> Dict[str, Dict[str, Any]]:
    """
    Generate test templates for all pressure types.

    Args:
        name: A descriptive name to use in all templates.

    Returns:
        A dictionary mapping pressure type names to their templates.
    """
    return {
        ptype.value: generate_pressure_test_template(ptype, name)
        for ptype in PressureType
    }


def get_pressure_description(pressure_type: PressureType) -> str:
    """
    Get the human-readable description for a pressure type.

    Args:
        pressure_type: The pressure type to describe.

    Returns:
        A string description.
    """
    return PRESSURE_DESCRIPTIONS.get(pressure_type, "No description available.")


# Convenience list for backward compatibility and easy iteration
PRESSURE_TYPES = PressureType.list_types()