"""A simple counter module with a single function that increments a counter value.
This serves as the trivial capability to be evolved in the smoke test.
"""

_counter = 0

def increment_counter(step: int = 1) -> int:
    """Increment the global counter by the given step and return the new value.
    
    Args:
        step: The amount to increment by (default 1).
        
    Returns:
        The new counter value after incrementing.
    """
    global _counter
    _counter += step
    return _counter

def get_counter() -> int:
    """Return the current counter value without modifying it."""
    return _counter

def reset_counter() -> None:
    """Reset the counter to zero."""
    global _counter
    _counter = 0