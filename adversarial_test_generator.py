"""Module for analyzing agent solution patterns and generating adversarial test cases."""

import random
import string
from typing import Any, Callable, List, Tuple, Dict, Optional
from collections import Counter
import inspect


class PatternAnalyzer:
    """Analyzes solution code to detect patterns and potential weaknesses."""
    
    def __init__(self, source_code: str):
        self.source_code = source_code
        self.patterns = self._analyze_patterns()
    
    def _analyze_patterns(self) -> Dict[str, Any]:
        """Detect common algorithmic patterns in the source code."""
        patterns = {
            'sorting': self._detect_sorting(),
            'searching': self._detect_searching(),
            'recursion': self._detect_recursion(),
            'data_structures': self._detect_data_structures(),
            'loops': self._detect_loop_patterns(),
        }
        return patterns
    
    def _detect_sorting(self) -> Optional[str]:
        """Detect sorting algorithm patterns."""
        code = self.source_code.lower()
        if 'sorted(' in code or '.sort()' in code:
            return 'builtin_sort'
        if 'bubble' in code:
            return 'bubble_sort'
        if 'quick' in code or 'partition' in code:
            return 'quick_sort'
        if 'merge' in code:
            return 'merge_sort'
        if 'insertion' in code:
            return 'insertion_sort'
        if 'selection' in code:
            return 'selection_sort'
        if 'heap' in code:
            return 'heap_sort'
        return None
    
    def _detect_searching(self) -> Optional[str]:
        """Detect searching algorithm patterns."""
        code = self.source_code.lower()
        if 'binary_search' in code or 'bisect' in code:
            return 'binary_search'
        if 'linear_search' in code or 'in' in code:
            return 'linear_search'
        if 'hash' in code or 'dict' in code:
            return 'hash_based_search'
        return None
    
    def _detect_recursion(self) -> bool:
        """Detect if recursion is used."""
        return 'def ' in self.source_code and self._has_recursive_call()
    
    def _has_recursive_call(self) -> bool:
        """Check if any function calls itself."""
        lines = self.source_code.split('\n')
        func_names = []
        for line in lines:
            if line.strip().startswith('def '):
                func_name = line.split('def ')[1].split('(')[0].strip()
                func_names.append(func_name)
        for func_name in func_names:
            if func_name in self.source_code.split('def ' + func_name)[1] if len(self.source_code.split('def ' + func_name)) > 1 else '':
                return True
        return False
    
    def _detect_data_structures(self) -> List[str]:
        """Detect data structure usage patterns."""
        structures = []
        code = self.source_code.lower()
        if 'list' in code or '[' in code:
            structures.append('list')
        if 'dict' in code or '{' in code:
            structures.append('dict')
        if 'set' in code:
            structures.append('set')
        if 'tuple' in code or '(' in code:
            structures.append('tuple')
        if 'deque' in code:
            structures.append('deque')
        if 'heapq' in code:
            structures.append('heap')
        return structures
    
    def _detect_loop_patterns(self) -> Dict[str, bool]:
        """Detect loop patterns that might indicate performance issues."""
        code = self.source_code.lower()
        return {
            'nested_loops': code.count('for ') > 1 or code.count('while ') > 1,
            'infinite_loop_risk': 'while true' in code or 'while 1' in code,
            'range_loop': 'range(' in code,
            'enumerate_loop': 'enumerate(' in code,
        }


class AdversarialTestGenerator:
    """Generates adversarial test cases based on detected patterns."""
    
    def __init__(self, pattern_analyzer: PatternAnalyzer):
        self.analyzer = pattern_analyzer
        self.patterns = pattern_analyzer.patterns
    
    def generate_tests(self, num_tests: int = 5) -> List[Dict[str, Any]]:
        """Generate a set of adversarial test cases."""
        tests = []
        
        # Generate tests based on detected patterns
        if self.patterns['sorting']:
            tests.extend(self._generate_sorting_tests(num_tests))
        
        if self.patterns['searching']:
            tests.extend(self._generate_searching_tests(num_tests))
        
        if self.patterns['recursion']:
            tests.extend(self._generate_recursion_tests(num_tests))
        
        if 'list' in self.patterns['data_structures']:
            tests.extend(self._generate_list_tests(num_tests))
        
        if 'dict' in self.patterns['data_structures']:
            tests.extend(self._generate_dict_tests(num_tests))
        
        # Add general edge case tests
        tests.extend(self._generate_edge_case_tests(num_tests // 2))
        
        return tests[:num_tests * 3]  # Limit total tests
    
    def _generate_sorting_tests(self, count: int) -> List[Dict[str, Any]]:
        """Generate adversarial sorting tests."""
        tests = []
        sort_type = self.patterns['sorting']
        
        # Reverse-sorted input (worst case for many algorithms)
        tests.append({
            'type': 'sorting',
            'name': 'reverse_sorted',
            'input': list(range(1000, 0, -1)),
            'description': 'Reverse-sorted array - worst case for many sorting algorithms',
            'expected_behavior': 'Should handle large reverse-sorted input efficiently'
        })
        
        # Nearly sorted with few out-of-place elements
        tests.append({
            'type': 'sorting',
            'name': 'nearly_sorted',
            'input': self._generate_nearly_sorted(1000),
            'description': 'Nearly sorted array with few inversions',
            'expected_behavior': 'Should handle nearly sorted data efficiently'
        })
        
        # All identical elements
        tests.append({
            'type': 'sorting',
            'name': 'all_equal',
            'input': [42] * 1000,
            'description': 'All elements identical - tests stability and duplicate handling',
            'expected_behavior': 'Should handle duplicate elements correctly'
        })
        
        # Large dataset with random values
        tests.append({
            'type': 'sorting',
            'name': 'large_random',
            'input': [random.randint(-10000, 10000) for _ in range(10000)],
            'description': 'Large random dataset - tests performance under load',
            'expected_behavior': 'Should sort large datasets efficiently'
        })
        
        # Mixed types (if allowed)
        tests.append({
            'type': 'sorting',
            'name': 'mixed_types',
            'input': [1, 'a', 2, 'b', 3, 'c'],
            'description': 'Mixed data types - tests type handling',
            'expected_behavior': 'Should handle or gracefully reject mixed types'
        })
        
        return tests
    
    def _generate_searching_tests(self, count: int) -> List[Dict[str, Any]]:
        """Generate adversarial searching tests."""
        tests = []
        search_type = self.patterns['searching']
        
        # Element not present
        tests.append({
            'type': 'searching',
            'name': 'element_not_found',
            'input': {
                'data': list(range(1000)),
                'target': 1500
            },
            'description': 'Search for element not in collection',
            'expected_behavior': 'Should return appropriate not-found indicator'
        })
        
        # Empty collection
        tests.append({
            'type': 'searching',
            'name': 'empty_collection',
            'input': {
                'data': [],
                'target': 42
            },
            'description': 'Search in empty collection',
            'expected_behavior': 'Should handle empty input gracefully'
        })
        
        # Duplicate elements
        tests.append({
            'type': 'searching',
            'name': 'duplicate_elements',
            'input': {
                'data': [1, 2, 2, 2, 3, 4, 5],
                'target': 2
            },
            'description': 'Search with duplicate elements',
            'expected_behavior': 'Should find first or any occurrence'
        })
        
        return tests
    
    def _generate_recursion_tests(self, count: int) -> List[Dict[str, Any]]:
        """Generate adversarial recursion tests."""
        tests = []
        
        # Deep recursion test
        tests.append({
            'type': 'recursion',
            'name': 'deep_recursion',
            'input': list(range(10000)),
            'description': 'Deep recursion - tests for stack overflow',
            'expected_behavior': 'Should handle deep recursion or convert to iterative'
        })
        
        # Recursion with large state
        tests.append({
            'type': 'recursion',
            'name': 'large_state_recursion',
            'input': [{'id': i, 'data': 'x' * 1000} for i in range(100)],
            'description': 'Recursion with large state objects',
            'expected_behavior': 'Should manage memory efficiently'
        })
        
        return tests
    
    def _generate_list_tests(self, count: int) -> List[Dict[str, Any]]:
        """Generate adversarial list operation tests."""
        tests = []
        
        # Very large list
        tests.append({
            'type': 'list',
            'name': 'large_list',
            'input': list(range(100000)),
            'description': 'Very large list - tests memory and performance',
            'expected_behavior': 'Should handle large lists efficiently'
        })
        
        # List with None values
        tests.append({
            'type': 'list',
            'name': 'list_with_none',
            'input': [1, None, 2, None, 3],
            'description': 'List containing None values',
            'expected_behavior': 'Should handle None values appropriately'
        })
        
        # Nested list structure
        tests.append({
            'type': 'list',
            'name': 'nested_list',
            'input': [[1, 2], [3, [4, 5]], 6],
            'description': 'Nested list structure - tests recursive handling',
            'expected_behavior': 'Should handle nested structures correctly'
        })
        
        return tests
    
    def _generate_dict_tests(self, count: int) -> List[Dict[str, Any]]:
        """Generate adversarial dictionary tests."""
        tests = []
        
        # Large dictionary
        tests.append({
            'type': 'dict',
            'name': 'large_dict',
            'input': {str(i): i for i in range(10000)},
            'description': 'Large dictionary - tests hash table performance',
            'expected_behavior': 'Should handle large dictionaries efficiently'
        })
        
        # Dictionary with hash collisions
        tests.append({
            'type': 'dict',
            'name': 'hash_collision',
            'input': {i: i for i in range(1000)},
            'description': 'Dictionary with potential hash collisions',
            'expected_behavior': 'Should handle hash collisions gracefully'
        })
        
        # Dictionary with mixed key types
        tests.append({
            'type': 'dict',
            'name': 'mixed_keys',
            'input': {1: 'a', '1': 'b', (1,): 'c'},
            'description': 'Dictionary with mixed key types',
            'expected_behavior': 'Should handle different key types'
        })
        
        return tests
    
    def _generate_edge_case_tests(self, count: int) -> List[Dict[str, Any]]:
        """Generate general edge case tests."""
        tests = []
        
        # Empty input
        tests.append({
            'type': 'edge_case',
            'name': 'empty_input',
            'input': None,
            'description': 'Empty input - tests null handling',
            'expected_behavior': 'Should handle None/empty input gracefully'
        })
        
        # Single element
        tests.append({
            'type': 'edge_case',
            'name': 'single_element',
            'input': [42],
            'description': 'Single element input',
            'expected_behavior': 'Should handle single element correctly'
        })
        
        # Very large values
        tests.append({
            'type': 'edge_case',
            'name': 'large_values',
            'input': [10**18, -10**18, 2**63 - 1],
            'description': 'Very large numeric values',
            'expected_behavior': 'Should handle large numbers without overflow'
        })
        
        # Special characters
        tests.append({
            'type': 'edge_case',
            'name': 'special_characters',
            'input': ['', '\n', '\t', '\\', '"', "'"],
            'description': 'Strings with special characters',
            'expected_behavior': 'Should handle special characters correctly'
        })
        
        return tests
    
    def _generate_nearly_sorted(self, size: int, inversions: int = 10) -> List[int]:
        """Generate a nearly sorted list with few inversions."""
        arr = list(range(size))
        for _ in range(inversions):
            i, j = random.sample(range(size), 2)
            arr[i], arr[j] = arr[j], arr[i]
        return arr


def analyze_and_generate_tests(source_code: str, num_tests: int = 5) -> List[Dict[str, Any]]:
    """Convenience function to analyze code and generate adversarial tests."""
    analyzer = PatternAnalyzer(source_code)
    generator = AdversarialTestGenerator(analyzer)
    return generator.generate_tests(num_tests)


def print_test_summary(tests: List[Dict[str, Any]]) -> None:
    """Print a summary of generated tests."""
    print(f"Generated {len(tests)} adversarial test cases:")
    print("-" * 60)
    
    for i, test in enumerate(tests, 1):
        print(f"\nTest {i}: {test['name']}")
        print(f"  Type: {test['type']}")
        print(f"  Description: {test['description']}")
        print(f"  Expected: {test['expected_behavior']}")
        if isinstance(test.get('input'), list) and len(test['input']) > 10:
            print(f"  Input size: {len(test['input'])} elements")
        else:
            print(f"  Input: {test.get('input')}")


# Example usage
if __name__ == "__main__":
    # Example solution code to analyze
    example_code = """
def sort_numbers(arr):
    return sorted(arr)

def find_element(arr, target):
    for i, val in enumerate(arr):
        if val == target:
            return i
    return -1

def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
    
    tests = analyze_and_generate_tests(example_code, num_tests=3)
    print_test_summary(tests)