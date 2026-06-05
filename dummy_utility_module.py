"""
dummy_utility_module.py

A simple, safe dummy utility module for integration testing.
Provides basic math helper functions with predictable behavior.
"""

import math

def add(a: float, b: float) -> float:
    """Return the sum of a and b."""
    return a + b

def subtract(a: float, b: float) -> float:
    """Return the result of a minus b."""
    return a - b

def multiply(a: float, b: float) -> float:
    """Return the product of a and b."""
    return a * b

def divide(a: float, b: float) -> float:
    """Return a divided by b. Raises ZeroDivisionError if b is zero."""
    if b == 0:
        raise ZeroDivisionError("division by zero is not allowed")
    return a / b

def power(base: float, exponent: float) -> float:
    """Return base raised to the power of exponent."""
    return base ** exponent

def square_root(x: float) -> float:
    """Return the square root of x. Raises ValueError for negative input."""
    if x < 0:
        raise ValueError("cannot compute square root of negative number")
    return math.sqrt(x)

def factorial(n: int) -> int:
    """Return the factorial of n (n!). n must be a non-negative integer."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("factorial requires a non-negative integer")
    return math.factorial(n)

def is_even(n: int) -> bool:
    """Return True if n is even, False otherwise."""
    return n % 2 == 0

def is_odd(n: int) -> bool:
    """Return True if n is odd, False otherwise."""
    return n % 2 != 0

def mean(numbers: list) -> float:
    """Return the arithmetic mean of a list of numbers. Raises ValueError for empty list."""
    if not numbers:
        raise ValueError("cannot compute mean of empty list")
    return sum(numbers) / len(numbers)

# Test file content (optional, can be placed in a separate test file)
# For convenience, a basic test function is included here.
# In practice, use a dedicated test framework like pytest or unittest.

def run_basic_tests():
    """Run a few basic tests to verify function behavior."""
    assert add(2, 3) == 5, "add test failed"
    assert subtract(10, 4) == 6, "subtract test failed"
    assert multiply(3, 7) == 21, "multiply test failed"
    assert divide(15, 3) == 5, "divide test failed"
    try:
        divide(1, 0)
        assert False, "divide by zero should raise error"
    except ZeroDivisionError:
        pass
    assert power(2, 3) == 8, "power test failed"
    assert square_root(9) == 3, "square_root test failed"
    try:
        square_root(-1)
        assert False, "square_root negative should raise error"
    except ValueError:
        pass
    assert factorial(5) == 120, "factorial test failed"
    assert is_even(4) == True, "is_even test failed"
    assert is_odd(3) == True, "is_odd test failed"
    assert mean([1, 2, 3, 4]) == 2.5, "mean test failed"
    try:
        mean([])
        assert False, "mean empty list should raise error"
    except ValueError:
        pass
    print("All basic tests passed.")

if __name__ == "__main__":
    run_basic_tests()