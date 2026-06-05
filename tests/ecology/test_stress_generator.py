"""Stress test generator for the ecology engine.
Produces tests with high concurrency, large input data, and edge cases.
This is one of the first 'novel' test types the ecology engine introduces."""

import asyncio
import random
import string
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# Data generators for large / edge-case inputs
# ---------------------------------------------------------------------------

def generate_large_string(size: int = 10_000) -> str:
    """Generate a random string of given size (default 10k characters)."""
    return ''.join(random.choices(string.printable, k=size))


def generate_large_list(size: int = 5_000) -> List[int]:
    """Generate a list of random integers of given size (default 5k elements)."""
    return [random.randint(-10**6, 10**6) for _ in range(size)]


def generate_large_dict(size: int = 1_000) -> Dict[str, int]:
    """Generate a dictionary with `size` entries."""
    return {f"key_{i}": random.randint(0, 1000) for i in range(size)}


def generate_nested_structure(depth: int = 5, breadth: int = 3) -> Any:
    """Generate a deeply nested list/dict structure."""
    if depth <= 0:
        return random.choice([None, 0, "", [], {}])
    return [
        {f"nested_key_{j}": generate_nested_structure(depth - 1, breadth)}
        for j in range(breadth)
    ]


# ---------------------------------------------------------------------------
# Edge-case input generators
# ---------------------------------------------------------------------------

def edge_case_inputs() -> List[Any]:
    """Return a list of common edge-case values."""
    return [
        None,
        "",
        [],
        {},
        0,
        -1,
        float('inf'),
        float('-inf'),
        float('nan'),
        b'',
        (),
        set(),
        frozenset(),
        object(),
    ]


# ---------------------------------------------------------------------------
# Concurrency helpers
# ---------------------------------------------------------------------------

async def run_concurrent_calls(
    func: Callable,
    args_list: List[Tuple],
    concurrency: int = 10,
) -> List[Any]:
    """Execute `func` concurrently with each tuple in `args_list`."""
    semaphore = asyncio.Semaphore(concurrency)

    async def limited_call(*args):
        async with semaphore:
            if asyncio.iscoroutinefunction(func):
                return await func(*args)
            else:
                # Run sync function in executor to avoid blocking
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, func, *args)

    tasks = [limited_call(*args) for args in args_list]
    return await asyncio.gather(*tasks, return_exceptions=True)


# ---------------------------------------------------------------------------
# Stress test case builder
# ---------------------------------------------------------------------------

class StressTestCase:
    """Represents a single stress test case with metadata."""

    def __init__(
        self,
        name: str,
        target_module: str,
        input_data: Any,
        concurrency_level: int = 1,
        description: str = "",
    ):
        self.name = name
        self.target_module = target_module
        self.input_data = input_data
        self.concurrency_level = concurrency_level
        self.description = description

    def __repr__(self) -> str:
        return (
            f"StressTestCase(name={self.name!r}, "
            f"module={self.target_module!r}, "
            f"concurrency={self.concurrency_level})"
        )


def generate_stress_test_cases(
    target_modules: Optional[List[str]] = None,
    num_large_data_tests: int = 5,
    num_concurrency_tests: int = 5,
    num_edge_case_tests: int = 10,
) -> List[StressTestCase]:
    """Generate a collection of stress test cases.

    Parameters
    ----------
    target_modules : list of str, optional
        Module names to target. Defaults to common modules.
    num_large_data_tests : int
        Number of tests with large input data.
    num_concurrency_tests : int
        Number of high-concurrency tests.
    num_edge_case_tests : int
        Number of edge-case tests.

    Returns
    -------
    list of StressTestCase
    """
    if target_modules is None:
        target_modules = [
            "core.ecology_engine",
            "modules.meta_cognitive_evaluator",
            "modules.test_generator",
            "modules.quality_metrics",
        ]

    cases: List[StressTestCase] = []

    # 1) Large data tests
    for i in range(num_large_data_tests):
        module = random.choice(target_modules)
        data_type = random.choice(["string", "list", "dict", "nested"])
        if data_type == "string":
            data = generate_large_string(random.randint(5_000, 50_000))
        elif data_type == "list":
            data = generate_large_list(random.randint(1_000, 10_000))
        elif data_type == "dict":
            data = generate_large_dict(random.randint(100, 2_000))
        else:
            data = generate_nested_structure(random.randint(3, 7), random.randint(2, 5))

        cases.append(StressTestCase(
            name=f"large_data_{data_type}_{i}",
            target_module=module,
            input_data=data,
            concurrency_level=1,
            description=f"Large {data_type} input test #{i}",
        ))

    # 2) High concurrency tests
    for i in range(num_concurrency_tests):
        module = random.choice(target_modules)
        concurrency = random.choice([10, 25, 50, 100])
        # Create a list of identical calls to simulate high load
        data = [{"call_id": j, "payload": f"concurrent_payload_{j}"} for j in range(concurrency)]
        cases.append(StressTestCase(
            name=f"high_concurrency_{concurrency}_{i}",
            target_module=module,
            input_data=data,
            concurrency_level=concurrency,
            description=f"High concurrency test with {concurrency} simultaneous calls",
        ))

    # 3) Edge case tests
    edge_values = edge_case_inputs()
    for i in range(num_edge_case_tests):
        module = random.choice(target_modules)
        # Pick a random edge value, sometimes wrap in container
        choice = random.choice(edge_values)
        if random.random() < 0.3:
            # Wrap in a list or dict for extra edge
            if random.random() < 0.5:
                data = [choice]
            else:
                data = {"edge": choice}
        else:
            data = choice

        cases.append(StressTestCase(
            name=f"edge_case_{type(data).__name__}_{i}",
            target_module=module,
            input_data=data,
            concurrency_level=1,
            description=f"Edge case with value type {type(data).__name__}",
        ))

    return cases


# ---------------------------------------------------------------------------
# Async stress test runner
# ---------------------------------------------------------------------------

async def run_stress_test_suite(
    cases: List[StressTestCase],
    module_function_map: Dict[str, Callable],
    global_concurrency_limit: int = 20,
) -> Dict[str, Any]:
    """Execute a list of stress test cases concurrently.

    Parameters
    ----------
    cases : list of StressTestCase
        The test cases to run.
    module_function_map : dict
        Mapping from module name (string) to a callable that accepts input_data.
    global_concurrency_limit : int
        Maximum number of concurrent test executions overall.

    Returns
    -------
    dict with keys:
        - 'results': list of (case_name, result_or_exception)
        - 'total_cases': int
        - 'passed': int
        - 'failed': int
    """
    semaphore = asyncio.Semaphore(global_concurrency_limit)

    async def run_single(case: StressTestCase) -> Tuple[str, Any]:
        async with semaphore:
            func = module_function_map.get(case.target_module)
            if func is None:
                return (case.name, ModuleNotFoundError(f"No function for {case.target_module}"))

            try:
                if case.concurrency_level > 1:
                    # For high concurrency, we run the function many times in parallel
                    args_list = [(item,) for item in case.input_data]
                    result = await run_concurrent_calls(
                        func, args_list, concurrency=case.concurrency_level
                    )
                else:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(case.input_data)
                    else:
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(None, func, case.input_data)
                return (case.name, result)
            except Exception as e:
                return (case.name, e)

    tasks = [run_single(case) for case in cases]
    results = await asyncio.gather(*tasks)

    passed = sum(1 for _, r in results if not isinstance(r, Exception))
    failed = sum(1 for _, r in results if isinstance(r, Exception))

    return {
        "results": results,
        "total_cases": len(cases),
        "passed": passed,
        "failed": failed,
    }


# ---------------------------------------------------------------------------
# Convenience: generate and run in one call
# ---------------------------------------------------------------------------

async def generate_and_run_stress_tests(
    module_function_map: Dict[str, Callable],
    num_large_data: int = 3,
    num_concurrency: int = 3,
    num_edge: int = 5,
    global_concurrency: int = 20,
) -> Dict[str, Any]:
    """Generate stress test cases and run them immediately."""
    cases = generate_stress_test_cases(
        target_modules=list(module_function_map.keys()),
        num_large_data_tests=num_large_data,
        num_concurrency_tests=num_concurrency,
        num_edge_case_tests=num_edge,
    )
    return await run_stress_test_suite(cases, module_function_map, global_concurrency)


# ---------------------------------------------------------------------------
# Example / test harness (if run directly)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Simple demonstration: define dummy functions for each module
    async def dummy_async(data):
        await asyncio.sleep(0.01)
        return f"processed {type(data).__name__}"

    def dummy_sync(data):
        return f"sync processed {type(data).__name__}"

    dummy_map = {
        "core.ecology_engine": dummy_async,
        "modules.meta_cognitive_evaluator": dummy_sync,
        "modules.test_generator": dummy_async,
        "modules.quality_metrics": dummy_sync,
    }

    async def main():
        result = await generate_and_run_stress_tests(
            dummy_map,
            num_large_data=2,
            num_concurrency=2,
            num_edge=3,
            global_concurrency=10,
        )
        print(f"Total cases: {result['total_cases']}")
        print(f"Passed: {result['passed']}")
        print(f"Failed: {result['failed']}")
        for name, res in result["results"]:
            status = "OK" if not isinstance(res, Exception) else f"ERROR: {res}"
            print(f"  {name}: {status}")

    asyncio.run(main())